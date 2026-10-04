"""Billing, WhatsApp, admin and health endpoints."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text

from app.ai.service import get_ai
from app.api.routes.admin import Staff
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.deps import DB, CurrentUser
from app.core.errors import AppError, NotFound
from app.jobs.queue import run_inline_if_configured
from app.models import (
    GenerationJob,
    Payment,
    Plan,
    Subscription,
    TrialGrant,
    User,
    WhatsAppContact,
    WhatsAppMessage,
)
from app.services import admin as admin_svc
from app.services import billing, usage
from app.services import whatsapp as wa
from app.services.events import audit, security_event
from app.services.settings import DEFAULTS, get_app_settings, set_setting

router = APIRouter()


# --------------------------------------------------------------------------- health


@router.get("/health", tags=["health"])
async def health():
    """Liveness: the process is up. Cheap, no dependencies, safe for a load balancer to poll often."""
    s = get_settings()
    return {"status": "ok", "version": s.app_version, "environment": s.environment}


@router.get("/ready", tags=["health"])
async def ready():
    """Readiness: dependencies are reachable and migrations are current. 503 until the instance can serve."""
    import time as _time

    checks: dict[str, Any] = {}
    status = 200
    t0 = _time.monotonic()
    try:
        async with get_sessionmaker()() as s:
            await s.execute(text("select 1"))
            from alembic.config import Config
            from alembic.script import ScriptDirectory

            from app.core.config import API_ROOT

            config = Config()
            config.set_main_option("script_location", str(API_ROOT / "alembic"))
            expected = set(ScriptDirectory.from_config(config).get_heads())
            exists = (await s.execute(text("select to_regclass('alembic_version')"))).scalar()
            applied = set((await s.execute(text("select version_num from alembic_version"))).scalars()) if exists else set()
            checks["migration"] = next(iter(applied), None)
            # Unit/integration fixtures build their schema directly from the models.
            current = applied == expected or (get_settings().environment == "test" and not exists)
            checks["schema"] = {"ok": current}
            if not current:
                status = 503
        checks["database"] = {"ok": True, "ms": int((_time.monotonic() - t0) * 1000)}
    except Exception:  # noqa: BLE001
        checks["database"] = {"ok": False}
        status = 503
    s = get_settings()
    if s.redis_url:
        try:
            from app.core.ratelimit import limiter

            await limiter._redis.ping()  # noqa: SLF001
            checks["redis"] = {"ok": True}
        except Exception:  # noqa: BLE001
            checks["redis"] = {"ok": False}
            status = 503
    ai = get_ai()
    checks["ai"] = {"mode": ai.mode, "providers": ai.live_providers,
                    "circuit_open": [p for p in ai.live_providers if ai.breaker.is_open(p)]}
    from fastapi.responses import JSONResponse

    return JSONResponse({"status": "ready" if status == 200 else "not_ready", "version": s.app_version,
                         "checks": checks}, status_code=status)


@router.get("/status", tags=["health"])
async def public_status(db: DB):
    """Public status page data: component health and active maintenance/incident notices. No internals."""
    from datetime import timedelta

    from app.core.db import utcnow
    from app.models import AIUsage, Announcement, GenerationJob
    from app.services.settings import get_setting_cached

    since = utcnow() - timedelta(minutes=30)
    ai_total, ai_ok = (await db.execute(select(func.count(), func.count().filter(AIUsage.success.is_(True)))
                                        .where(AIUsage.created_at >= since))).one()
    stuck = (await db.execute(select(func.count()).select_from(GenerationJob).where(
        GenerationJob.status == "queued", GenerationJob.created_at < utcnow() - timedelta(minutes=15)))).scalar_one()
    system = await get_setting_cached("system")
    notices = (await db.execute(select(Announcement).where(
        Announcement.active.is_(True), Announcement.kind.in_(("maintenance", "important")),
        Announcement.audience.in_(("everyone", "teachers")), Announcement.starts_at <= utcnow())
        .order_by(Announcement.starts_at.desc()).limit(3))).scalars().all()

    def state(ok: bool, degraded: bool = False) -> str:
        return "operational" if ok and not degraded else ("degraded" if ok else "outage")

    ai_rate = (ai_ok / ai_total) if ai_total else 1.0
    maintenance = (system.get("maintenance") or {}).get("enabled", False)
    return {
        "status": "maintenance" if maintenance else ("operational" if ai_rate >= 0.9 and not stuck else "degraded"),
        "components": {"web_app": state(not maintenance), "api": state(True),
                       "ai_generation": state(ai_rate >= 0.5, ai_rate < 0.9),
                       "generation_queue": state(stuck < 20, stuck > 0)},
        "notices": [{"title": a.title, "body": a.body, "kind": a.kind, "starts_at": a.starts_at.isoformat()}
                    for a in notices],
        "updated_at": utcnow().isoformat(),
    }


@router.get("/public/config", tags=["health"])
async def public_config():
    """Non-secret settings the web app needs before sign-in."""
    cfg = await get_app_settings(["ui", "system"])
    system = cfg["system"]
    return {"default_skin": cfg["ui"].get("default_skin", "forest"),
            "turnstile_site_key": get_settings().turnstile_site_key,
            "registration_enabled": system.get("registration_enabled", True),
            "maintenance": (system.get("maintenance") or {}).get("enabled", False),
            "version": get_settings().app_version}


# --------------------------------------------------------------------------- billing


def plan_out(p: Plan) -> dict[str, Any]:
    return {"code": p.code, "name": p.name, "price_monthly_aed": float(p.price_monthly_aed),
            "price_annual_aed": float(p.price_annual_aed), "limits": p.limits, "features": p.features}


@router.get("/billing/plans", tags=["billing"])
async def plans(db: DB):
    rows = (await db.execute(select(Plan).where(Plan.active.is_(True)).order_by(Plan.sort))).scalars().all()
    provider = await billing.active_provider_name()
    trial = (await get_app_settings(["trial"]))["trial"]
    return {"items": [plan_out(p) for p in rows], "currency": "AED", "vat_rate": 0.05,
            "online_payments": provider is not None, "payment_provider": provider,
            "trial": {"enabled": bool(trial.get("enabled")) and int(trial.get("days", 0)) > 0,
                      "plan": trial.get("plan", "pro"), "days": int(trial.get("days", 0)),
                      "credits": int(trial.get("credits", 50))}}


@router.get("/billing/subscription", tags=["billing"])
async def subscription(user: CurrentUser, db: DB):
    summary = await usage.summary(db, user)
    if summary["subscription"] is None:
        # Keep payment recovery and cancellation reachable after paid access
        # expires; this record does not change the user's Free entitlements.
        pending = await billing.manageable_online_subscription(db, user.id)
        if pending:
            summary["subscription"] = {
                "status": pending.status, "interval": pending.interval,
                "current_period_end": pending.current_period_end.isoformat() if pending.current_period_end else None,
                "cancel_at_period_end": pending.cancel_at_period_end, "provider": pending.provider,
            }
    await billing.lock_plan_changes(db, user.id)
    pending = await billing.pending_checkout(db, user.id, reconcile_expiry=True)
    await db.commit()
    summary["pending_checkout"] = {
        "id": str(pending.id), "provider": pending.provider, "status": pending.status,
        "plan": pending.plan_code, "interval": pending.interval,
        "url": pending.checkout_url, "expires_at": pending.expires_at.isoformat(),
    } if pending else None
    cfg = (await get_app_settings(["trial"]))["trial"]
    summary["trial_available"] = bool(user.email_verified and user.role != "admin" and cfg.get("enabled")
        and int(cfg.get("days", 0)) > 0 and not summary["subscription"] and not pending and not summary.get("trial"))
    if summary["trial_available"]:
        from app.api.routes.auth import normalised_email_hash

        previous_trial = (await db.execute(select(TrialGrant.id).where(
            TrialGrant.email_hash == normalised_email_hash(user.email)))).first()
        summary["trial_available"] = previous_trial is None
    pays = (await db.execute(select(Payment).where(Payment.user_id == user.id).order_by(Payment.created_at.desc())
                             .limit(24))).scalars().all()
    summary["payments"] = [{"amount": float(p.amount), "currency": p.currency, "tax": float(p.tax_amount),
                            "status": p.status, "invoice_url": p.invoice_url, "date": p.created_at.isoformat()}
                           for p in pays]
    return summary


class CheckoutIn(BaseModel):
    plan: str
    interval: str = Field("month", pattern="^(month|year)$")
    coupon_code: str | None = Field(None, max_length=100)


@router.post("/billing/checkout", tags=["billing"])
async def checkout(data: CheckoutIn, user: CurrentUser, db: DB):
    url = await billing.start_checkout(db, user, data.plan, data.interval, data.coupon_code)
    from app.services.events import track

    track(db, "checkout_started", user_id=user.id, plan=data.plan, interval=data.interval)
    await db.commit()
    return {"url": url}


@router.post("/billing/portal", tags=["billing"])
async def portal(user: CurrentUser, db: DB):
    return {"url": await billing.open_portal(db, user)}


@router.post("/billing/checkout/cancel", tags=["billing"])
async def cancel_checkout(user: CurrentUser, db: DB):
    await billing.cancel_pending_checkout(db, user.id)
    return {"ok": True}


@router.post("/billing/cancel", tags=["billing"])
async def cancel(user: CurrentUser, db: DB):
    sub = await billing.cancel_subscription(db, user)
    return {"status": sub.status, "cancel_at_period_end": sub.cancel_at_period_end}


@router.post("/webhooks/stripe", tags=["webhooks"])
async def stripe_webhook(request: Request, db: DB):
    payload = await request.body()
    try:
        event = (await billing.get_provider("stripe")).verify(payload, request.headers.get("stripe-signature"))
    except AppError as e:
        await _reject_webhook(db, request, "stripe", e)
        raise
    result = await billing.process_webhook(db, provider="stripe", event_id=event["id"], event_type=event["type"],
                                           event=event, raw=payload, handler=billing.handle_stripe_event,
                                           request=request)
    return {"received": True, "result": result}


async def _reject_webhook(db, request: Request, provider: str, e: AppError) -> None:
    if e.code == "invalid_signature":
        security_event(db, "webhook_rejected", request=request, provider=provider, reason=e.code)
        await db.commit()


@router.post("/webhooks/dodo", tags=["webhooks"])
async def dodo_webhook(request: Request, db: DB):
    """Dodo Payments events, signed with Standard Webhooks (webhook-id / webhook-timestamp / webhook-signature)."""
    payload = await request.body()
    headers = {k: request.headers.get(k, "") for k in ("webhook-id", "webhook-timestamp", "webhook-signature")}
    try:
        event = billing.verify_dodo_webhook(payload, headers)
    except AppError as e:
        await _reject_webhook(db, request, "dodo", e)
        raise
    result = await billing.process_webhook(db, provider="dodo", event_id=headers["webhook-id"],
                                           event_type=event.get("type", ""), event=event, raw=payload,
                                           handler=billing.handle_dodo_event, request=request)
    return {"received": True, "result": result}


# --------------------------------------------------------------------------- WhatsApp


@router.get("/whatsapp", tags=["whatsapp"])
async def whatsapp_status(user: CurrentUser, db: DB):
    contact = (await db.execute(select(WhatsAppContact).where(WhatsAppContact.user_id == user.id))).scalars().first()
    msgs = (await db.execute(select(WhatsAppMessage).where(WhatsAppMessage.user_id == user.id)
                             .order_by(WhatsAppMessage.created_at.desc()).limit(30))).scalars().all()
    plan, _ = await usage.get_plan(db, user)
    return {"enabled_on_plan": bool(plan.limits.get("whatsapp_messages")) or user.role == "admin",
            "live": wa.WhatsAppClient().enabled,
            "simulation_enabled": not get_settings().is_production,
            "contact": None if contact is None else {
                "phone": contact.phone_e164, "verified": contact.verified, "opted_in": contact.opted_in,
                "daily_time": contact.daily_time, "reflection_time": contact.reflection_time,
                "quiet_start": contact.quiet_start, "quiet_end": contact.quiet_end,
                "pending_code": contact.verification_code},
            "messages": [{"direction": m.direction, "body": m.body, "status": m.status, "template": m.template,
                          "category": m.category, "created_at": m.created_at.isoformat()} for m in msgs],
            "templates": wa.TEMPLATES}


class LinkIn(BaseModel):
    phone: str


@router.post("/whatsapp/link", tags=["whatsapp"])
async def whatsapp_link(data: LinkIn, user: CurrentUser, db: DB):
    return await wa.start_link(db, user, data.phone)


class WaSettingsIn(BaseModel):
    daily_time: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    reflection_time: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    quiet_start: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    quiet_end: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    opted_in: bool | None = None


@router.put("/whatsapp/settings", tags=["whatsapp"])
async def whatsapp_settings(data: WaSettingsIn, user: CurrentUser, db: DB):
    contact = (await db.execute(select(WhatsAppContact).where(WhatsAppContact.user_id == user.id))).scalars().first()
    if contact is None:
        raise NotFound("WhatsApp contact")
    for k, v in data.model_dump(exclude_none=True).items():
        if k == "opted_in" and v and not contact.verified:
            raise AppError("not_verified", "Link your number first.", 400)
        setattr(contact, k, v)
    await db.commit()
    return {"ok": True}


@router.post("/whatsapp/unlink", tags=["whatsapp"])
async def whatsapp_unlink(user: CurrentUser, db: DB):
    contact = (await db.execute(select(WhatsAppContact).where(WhatsAppContact.user_id == user.id))).scalars().first()
    if contact:
        await db.delete(contact)
        await db.commit()
    return {"ok": True}


@router.post("/whatsapp/simulate", tags=["whatsapp"])
async def whatsapp_simulate(user: CurrentUser, db: DB, body: dict[str, Any]):
    """Dev/demo only: pretend the teacher sent a WhatsApp message (when no live WhatsApp is configured)."""
    if get_settings().is_production:
        raise AppError("forbidden", "Simulation is disabled in production.", 403)
    contact = (await db.execute(select(WhatsAppContact).where(WhatsAppContact.user_id == user.id))).scalars().first()
    if contact is None:
        raise NotFound("WhatsApp contact")
    msg = {"from": contact.phone_e164.lstrip("+"), "id": f"sim-in-{uuid.uuid4().hex[:12]}"}
    if body.get("payload"):
        msg.update({"type": "button", "button": {"text": body.get("text", ""), "payload": body["payload"]}})
    else:
        msg.update({"type": "text", "text": {"body": body.get("text", "")}})
    await wa.handle_inbound(db, msg)
    await db.commit()
    await run_inline_if_configured([])
    return await whatsapp_status(user, db)


@router.post("/whatsapp/send-today", tags=["whatsapp"])
async def whatsapp_send_today(user: CurrentUser, db: DB):
    contact = (await db.execute(select(WhatsAppContact).where(WhatsAppContact.user_id == user.id))).scalars().first()
    if contact is None or not contact.verified:
        raise AppError("not_verified", "Link your WhatsApp number first.", 400)
    from app.services.planner import today_for

    classes, short = await wa.today_summary(db, user, today_for(user))
    msg = await wa.send_template(db, user, contact, "daily_plan_morning",
                                 [user.name.split(" ")[0] or "teacher", str(len(classes)), short[:500]],
                                 ["SHOW_TODAY", "OPEN_TODAY"])
    await db.commit()
    return {"sent": msg is not None, "status": msg.status if msg else "limit_reached"}


@router.get("/webhooks/whatsapp", tags=["webhooks"])
async def whatsapp_verify(request: Request):
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == get_settings().whatsapp_verify_token:
        return PlainTextResponse(q.get("hub.challenge", ""))
    raise AppError("forbidden", "Verification failed", 403)


@router.post("/webhooks/whatsapp", tags=["webhooks"])
async def whatsapp_webhook(request: Request, db: DB):
    raw = await request.body()
    if not wa.verify_signature(raw, request.headers.get("x-hub-signature-256")):
        raise AppError("invalid_signature", "Invalid signature", 401)
    handled = await wa.handle_webhook(db, json.loads(raw or b"{}"))
    return {"handled": handled}


# --------------------------------------------------------------------------- admin


@router.get("/admin/metrics", tags=["admin"])
async def admin_metrics(_: Staff("analytics.view"), db: DB, days: int = 30):
    return await admin_svc.metrics(db, min(days, 365))


@router.get("/admin/ai-costs", tags=["admin"])
async def admin_ai_costs(_: Staff("api_usage.view"), db: DB, days: int = 30):
    return await admin_svc.ai_costs(db, min(days, 365))


@router.get("/admin/plans", tags=["admin"])
async def admin_plans(_: Staff("billing.view"), db: DB):
    rows = (await db.execute(select(Plan).order_by(Plan.sort))).scalars().all()
    return {"items": [{**plan_out(p), "active": p.active} for p in rows]}


class PlanPatch(BaseModel):
    name: str | None = None
    price_monthly_aed: float | None = Field(None, ge=0)
    price_annual_aed: float | None = Field(None, ge=0)
    limits: dict[str, Any] | None = None
    features: list[str] | None = None
    active: bool | None = None


@router.put("/admin/plans/{code}", tags=["admin"])
async def admin_update_plan(code: str, data: PlanPatch, admin: Staff("billing.modify"), request: Request, db: DB):
    p = await db.get(Plan, code)
    if p is None:
        raise NotFound("Plan")
    before = plan_out(p)
    for k, v in data.model_dump(exclude_none=True).items():
        if k == "limits":
            v = {**p.limits, **v}
        setattr(p, k, v)
    audit(db, admin.id, "plan.updated", request=request, target_type="plan", target_id=code, before=before,
          after=plan_out(p))
    await db.commit()
    return plan_out(p)


@router.get("/admin/settings", tags=["admin"])
async def admin_settings(_: Staff("settings.modify")):
    return await get_app_settings()


def _validate_setting(key: str, value: dict[str, Any]) -> None:
    """Reject admin edits that would break checkout or the media studio."""

    def bad(msg: str) -> AppError:
        return AppError("invalid_setting", msg, 422)

    if key in ("ai_budget", "ai_rate_cards"):
        from pydantic import ValidationError

        from app.ai.budget import BudgetPolicy, RateCard

        try:
            if key == "ai_budget":
                BudgetPolicy.model_validate(value)
            else:
                for name, card in value.items():
                    if ":" not in name or name.split(":", 1)[0] not in ("openai", "anthropic", "gemini"):
                        raise bad("Price cards must be keyed by provider:model.")
                    RateCard.model_validate(card)
        except ValidationError as exc:
            raise bad(str(exc)) from exc
    elif key == "credit_costs":
        if any(type(v) is not int or v < 0 or v > 100000 for v in value.values()):
            raise bad("Credit costs must be whole numbers between 0 and 100000.")
    elif key == "billing":
        if value.get("provider", "auto") not in ("auto", "dodo", "stripe"):
            raise bad("Payment provider must be auto, dodo or stripe.")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in (value.get("dodo_products") or {}).items()):
            raise bad("Dodo product ids must be text.")
    elif key == "media":
        for field in ("image_credits", "video_credits_per_second"):
            if field in value and (not isinstance(value[field], int) or value[field] < 0):
                raise bad(f"{field} must be a whole number of credits (0 or more).")
        secs = value.get("video_seconds", [4, 8])
        if not secs or not all(isinstance(x, int) and 1 <= x <= 20 for x in secs):
            raise bad("Video lengths must be whole seconds between 1 and 20.")
        codes = set()
        for p in value.get("packs", []):
            if not p.get("code") or not p.get("name") or p["code"] in codes:
                raise bad("Every pack needs a unique code and a name.")
            if not isinstance(p.get("credits"), int) or p["credits"] <= 0:
                raise bad(f"Pack {p['code']}: credits must be a positive whole number.")
            if not isinstance(p.get("price_aed", 0), int | float) or p.get("price_aed", 0) < 0:
                raise bad(f"Pack {p['code']}: price must be a number.")
            codes.add(p["code"])
        for field in ("image_model", "video_model"):
            if value.get(field) and ":" not in value[field]:
                raise bad(f"{field} must look like provider:model, e.g. openai:sora-2.")
    elif key == "referrals":
        if type(value.get("enabled", True)) is not bool:
            raise bad("Referral enabled must be true or false.")
        reward = value.get("reward_media_credits", 25)
        if type(reward) is not int or not 1 <= reward <= 10000:
            raise bad("Referral reward must be 1 to 10000 media credits.")
    elif key == "trial":
        if value.get("plan", "pro") not in ("teacher", "pro", "assistant"):
            raise bad("Trial plan must be teacher, pro or assistant.")
        if not isinstance(value.get("days", 7), int) or not 0 <= value.get("days", 7) <= 90:
            raise bad("Trial length must be 0 to 90 days.")
        for resource in ("credits", "ai_images", "whatsapp_messages"):
            if resource in value and (type(value[resource]) is not int or not 0 <= value[resource] <= 100000):
                raise bad(f"Trial {resource} must be a whole number from 0 to 100000.")
    elif key == "ui" and value.get("default_skin", "forest") not in ("classic", "forest"):
        raise bad("Theme must be classic or forest.")
    elif key == "system":
        m = value.get("maintenance") or {}
        if not isinstance(m, dict) or not isinstance(m.get("enabled", False), bool):
            raise bad("maintenance.enabled must be true or false.")
        if len(str(m.get("message") or "")) > 500:
            raise bad("Maintenance message is too long (500 characters max).")
        for flag in ("registration_enabled", "ai_generation_enabled", "require_email_verification_for_generation"):
            if flag in value and not isinstance(value[flag], bool):
                raise bad(f"{flag} must be true or false.")
        mb = value.get("max_upload_mb", 100)
        if not isinstance(mb, int) or not 1 <= mb <= 500:
            raise bad("max_upload_mb must be 1 to 500.")
        for k, days in (value.get("retention_days") or {}).items():
            if not isinstance(days, int) or not 7 <= days <= 3650:
                raise bad(f"Retention for {k} must be 7 to 3650 days.")
    elif key == "plan_limits":
        for plan, limits in value.items():
            if not isinstance(limits, dict):
                raise bad(f"Limits for {plan} must be an object.")
            for field in ("daily_generations", "max_concurrent_jobs", "max_upload_mb"):
                v = limits.get(field)
                if v is not None and (not isinstance(v, int) or v < 0 or v > 100000):
                    raise bad(f"{plan}.{field} must be a whole number (0 or more).")
    elif key == "rate_limits":
        for field, v in value.items():
            if not isinstance(v, int) or not 1 <= v <= 100000:
                raise bad(f"{field} must be a whole number between 1 and 100000.")


@router.put("/admin/settings/{key}", tags=["admin"])
async def admin_set_setting(key: str, value: dict[str, Any], admin: Staff("settings.modify"), request: Request,
                            db: DB):
    if key not in DEFAULTS:
        raise AppError("bad_request", "Unknown setting", 400)
    _validate_setting(key, value)
    before = (await get_app_settings([key]))[key]
    await set_setting(key, value)
    audit(db, admin.id, "setting.updated", request=request, target_type="setting", target_id=key, before=before,
          after=value)
    await db.commit()
    get_ai()._overrides_at = 0  # refresh model routing immediately
    return (await get_app_settings([key]))[key]


@router.get("/admin/jobs", tags=["admin"])
async def admin_jobs(_: Staff("system.logs.view"), db: DB, status: str | None = "failed", limit: int = 50):
    q = select(GenerationJob)
    if status:
        q = q.where(GenerationJob.status == status)
    rows = (await db.execute(q.order_by(GenerationJob.created_at.desc()).limit(min(limit, 200)))).scalars().all()
    return {"items": [{"id": str(j.id), "type": j.type, "status": j.status, "error": j.error, "attempts": j.attempts,
                       "owner_id": str(j.owner_id) if j.owner_id else None, "created_at": j.created_at.isoformat()}
                      for j in rows]}


@router.post("/admin/jobs/{job_id}/retry", tags=["admin"])
async def admin_retry(job_id: uuid.UUID, admin: Staff("system.logs.view"), request: Request, db: DB):
    j = await db.get(GenerationJob, job_id)
    if j is None:
        raise NotFound("Job")
    j.status, j.stage, j.error, j.attempts = "queued", "Queued (retry)", None, 0
    audit(db, admin.id, "job.retried", request=request, target_user=j.owner_id, target_type="job", target_id=str(j.id))
    await db.commit()
    await run_inline_if_configured([j.id])
    return {"ok": True}


@router.get("/admin/subscriptions", tags=["admin"])
async def admin_subscriptions(_: Staff("billing.view"), db: DB):
    rows = (await db.execute(select(Subscription, User.email).join(User, User.id == Subscription.user_id)
                             .order_by(Subscription.created_at.desc()).limit(200))).all()
    return {"items": [{"email": e, "plan": s.plan_code, "status": s.status, "interval": s.interval,
                       "provider": s.provider, "period_end": s.current_period_end.isoformat()
                       if s.current_period_end else None} for s, e in rows]}


@router.get("/admin/ai-budget", tags=["admin"])
async def ai_budget_status(_: Staff("api_usage.view"), db: DB):
    from app.ai.budget import dashboard

    return await dashboard(db)


class AIReconciliation(BaseModel):
    amount_usd: float = Field(ge=0, le=100000, allow_inf_nan=False)
    reference: str = Field(min_length=10, max_length=500)


@router.post("/admin/ai-budget/{call_id}/reconcile", tags=["admin"])
async def reconcile_ai_call(call_id: uuid.UUID, data: AIReconciliation, admin: Staff("settings.modify"),
                            request: Request, db: DB):
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from app.ai.budget import lock
    from app.models import AICallReservation, AIUsage

    await lock(db)
    row = await db.get(AICallReservation, call_id, with_for_update=True)
    if row is None:
        raise NotFound("AI call")
    if row.status not in ("pending", "uncertain"):
        raise AppError("already_reconciled", "This call has already been settled.", 409)
    if row.job_id:
        job = await db.get(GenerationJob, row.job_id, with_for_update=True)
        if job and job.status in ("queued", "running"):
            raise AppError("active_job", "Wait until this job has stopped before reconciling its charge.", 409)
    if row.status == "pending" and datetime.now(UTC) - row.created_at < timedelta(hours=24):
        raise AppError("active_call", "Unfinished calls must be at least 24 hours old before reconciliation.", 409)
    before = {"status": row.status, "reserved_usd": float(row.reserved_usd)}
    row.status = "reconciled"
    row.charged_usd = Decimal(str(data.amount_usd))
    row.note = data.reference
    if row.usage_id:
        entry = await db.get(AIUsage, row.usage_id, with_for_update=True)
        if entry:
            delta = data.amount_usd - entry.cost_usd
            entry.cost_usd = data.amount_usd
            if row.job_id:
                job = await db.get(GenerationJob, row.job_id, with_for_update=True)
                if job:
                    job.cost_usd = max(0, job.cost_usd + delta)
    audit(db, admin.id, "ai_call.reconciled", request=request, target_type="ai_call", target_id=str(row.id),
          before=before, after=data.model_dump())
    await db.commit()
    return {"ok": True}


@router.get("/usage/estimates", tags=["usage"])
async def credit_estimates(user: CurrentUser, db: DB):
    from datetime import UTC, datetime

    from app.services.usage import get_plan, period_start, reserved, used

    plan, sub = await get_plan(db, user)
    since = period_start(sub)
    consumed = await used(db, user.id, "credits", since)
    held = await reserved(db, user.id)
    now = datetime.now(UTC)
    reset = now.replace(year=now.year + (now.month == 12), month=now.month % 12 + 1,
                        day=1, hour=0, minute=0, second=0, microsecond=0)
    if sub and sub.current_period_end and sub.current_period_end > now:
        reset = sub.current_period_end
    limit = plan.limits.get("credits")
    settings = await get_app_settings(["credit_costs"])
    return {"costs": settings["credit_costs"], "used": consumed, "reserved": held,
            "remaining": None if user.role == "admin" or limit is None or limit < 0 else max(0, limit - consumed - held),
            "reset_at": reset.isoformat(), "message": "Final credits depend on what you generate. Saved resources remain accessible."}


@router.get("/billing/referrals", tags=["billing"])
async def referrals(user: CurrentUser, db: DB):
    from app.services.engagement import referral_summary
    return await referral_summary(db, user)

# Single-use school / promotional plan licenses.
class LicenseCreateIn(BaseModel):
    plan: str = Field(pattern='^(teacher|pro|assistant)$')
    months: int = Field(1, ge=1, le=36)
    valid_days: int = Field(90, ge=1, le=365)

class LicenseRedeemIn(BaseModel):
    key: str = Field(min_length=10, max_length=100)

@router.post('/admin/licenses')
async def create_license(data: LicenseCreateIn, admin: Staff('billing.modify'), db: DB):
    from datetime import timedelta

    from app.core.db import utcnow
    from app.services.licenses import generate_key, key_digest
    if await db.get(Plan, data.plan) is None:
        raise AppError('invalid_plan', 'Plan does not exist.', 422)
    key, ident = generate_key(), uuid.uuid4()
    await db.execute(text('''INSERT INTO plan_licenses
        (id,key_hash,key_suffix,plan_code,months,expires_at,created_by)
        VALUES (:id,:digest,:suffix,:plan,:months,:expires,:actor)'''),
        dict(id=ident,digest=key_digest(key),suffix=key[-8:],plan=data.plan,
             months=data.months,expires=utcnow()+timedelta(days=data.valid_days),actor=admin.id))
    audit(db, admin.id, 'license.created', target_type='license', target_id=str(ident), plan=data.plan, months=data.months)
    await db.commit()
    return {'id': str(ident), 'key': key, 'plan': data.plan, 'months': data.months}

@router.get('/admin/licenses')
async def list_licenses(admin: Staff('billing.view'), db: DB):
    rows = (await db.execute(text('''SELECT id,key_suffix,plan_code,months,expires_at,redeemed_at,revoked
        FROM plan_licenses ORDER BY created_at DESC LIMIT 100'''))).mappings().all()
    return {'items': [dict(row) for row in rows]}

@router.delete('/admin/licenses/{license_id}')
async def revoke_license(license_id: uuid.UUID, admin: Staff('billing.modify'), db: DB):
    await db.execute(text('UPDATE plan_licenses SET revoked=true WHERE id=:id AND redeemed_at IS NULL'), {'id':license_id})
    audit(db, admin.id, 'license.revoked', target_type='license', target_id=str(license_id))
    await db.commit()
    return {'ok': True}

@router.post('/billing/licenses/redeem')
async def redeem_license(data: LicenseRedeemIn, user: CurrentUser, db: DB):
    from dateutil.relativedelta import relativedelta

    from app.core.db import utcnow
    from app.core.ratelimit import enforce
    from app.services.licenses import key_digest
    await enforce(f'license-redeem:{user.id}', 10, 3600)
    if user.role == 'admin' or not user.email_verified:
        raise AppError('license_ineligible', 'A verified teacher account is required.', 403)
    # Serialize plan changes for this teacher, and atomically consume a valid key.
    await billing.lock_plan_changes(db, user.id)
    if await usage.active_subscription(db, user.id) or await billing.pending_checkout(db, user.id, reconcile_expiry=True) or await billing.manageable_online_subscription(db, user.id):
        raise AppError('license_active_plan', 'Your current plan must end before you redeem a license. This avoids overlapping access or recurring charges.', 409)
    row = (await db.execute(text('''UPDATE plan_licenses SET redeemed_by=:user,redeemed_at=now()
        WHERE key_hash=:digest AND redeemed_at IS NULL AND revoked=false AND expires_at>now()
        RETURNING plan_code,months'''), {'user':user.id,'digest':key_digest(data.key)})).mappings().first()
    if row is None:
        raise AppError('invalid_license', 'License is invalid, expired, revoked or already used.', 422)
    now = utcnow()
    db.add(Subscription(user_id=user.id,plan_code=row['plan_code'],status='active',provider='manual',
        interval='month',current_period_start=now,current_period_end=now+relativedelta(months=row['months'])))
    await db.commit()
    return {'plan':row['plan_code'],'months':row['months']}
