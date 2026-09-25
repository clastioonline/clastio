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
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.deps import DB, AdminUser, CurrentUser
from app.core.errors import AppError, NotFound
from app.jobs.queue import run_inline_if_configured
from app.models import (
    AuditLog,
    Course,
    GenerationJob,
    Payment,
    Plan,
    Subscription,
    User,
    WhatsAppContact,
    WhatsAppMessage,
)
from app.services import admin as admin_svc
from app.services import billing, usage
from app.services import whatsapp as wa
from app.services.settings import DEFAULTS, get_app_settings, set_setting

router = APIRouter()


# --------------------------------------------------------------------------- health


@router.get("/health", tags=["health"])
async def health():
    db_ok = True
    try:
        async with get_sessionmaker()() as s:
            await s.execute(text("select 1"))
    except Exception:
        db_ok = False
    ai = get_ai()
    return {"status": "ok" if db_ok else "degraded", "database": db_ok, "ai_mode": ai.mode,
            "ai_providers": ai.live_providers, "environment": get_settings().environment}


@router.get("/public/config", tags=["health"])
async def public_config():
    """Non-secret settings the web app needs before sign-in."""
    ui = (await get_app_settings(["ui"]))["ui"]
    return {"default_skin": ui.get("default_skin", "classic")}


# --------------------------------------------------------------------------- billing


def plan_out(p: Plan) -> dict[str, Any]:
    return {"code": p.code, "name": p.name, "price_monthly_aed": float(p.price_monthly_aed),
            "price_annual_aed": float(p.price_annual_aed), "limits": p.limits, "features": p.features}


@router.get("/billing/plans", tags=["billing"])
async def plans(db: DB):
    rows = (await db.execute(select(Plan).where(Plan.active.is_(True)).order_by(Plan.sort))).scalars().all()
    provider = await billing.active_provider_name()
    return {"items": [plan_out(p) for p in rows], "currency": "AED", "vat_rate": 0.05,
            "online_payments": provider is not None, "payment_provider": provider}


@router.get("/billing/subscription", tags=["billing"])
async def subscription(user: CurrentUser, db: DB):
    summary = await usage.summary(db, user)
    pays = (await db.execute(select(Payment).where(Payment.user_id == user.id).order_by(Payment.created_at.desc())
                             .limit(24))).scalars().all()
    summary["payments"] = [{"amount": float(p.amount), "currency": p.currency, "tax": float(p.tax_amount),
                            "status": p.status, "invoice_url": p.invoice_url, "date": p.created_at.isoformat()}
                           for p in pays]
    return summary


class CheckoutIn(BaseModel):
    plan: str
    interval: str = Field("month", pattern="^(month|year)$")


@router.post("/billing/checkout", tags=["billing"])
async def checkout(data: CheckoutIn, user: CurrentUser, db: DB):
    return {"url": await billing.start_checkout(db, user, data.plan, data.interval)}


@router.post("/billing/portal", tags=["billing"])
async def portal(user: CurrentUser, db: DB):
    return {"url": await billing.open_portal(db, user)}


@router.post("/billing/cancel", tags=["billing"])
async def cancel(user: CurrentUser, db: DB):
    sub = await billing.cancel_subscription(db, user)
    return {"status": sub.status, "cancel_at_period_end": sub.cancel_at_period_end}


@router.post("/webhooks/stripe", tags=["webhooks"])
async def stripe_webhook(request: Request, db: DB):
    payload = await request.body()
    event = (await billing.get_provider("stripe")).verify(payload, request.headers.get("stripe-signature"))
    result = await billing.handle_stripe_event(db, event)
    return {"received": True, "result": result}


@router.post("/webhooks/dodo", tags=["webhooks"])
async def dodo_webhook(request: Request, db: DB):
    """Dodo Payments events, signed with Standard Webhooks (webhook-id / webhook-timestamp / webhook-signature)."""
    payload = await request.body()
    headers = {k: request.headers.get(k, "") for k in ("webhook-id", "webhook-timestamp", "webhook-signature")}
    event = billing.verify_dodo_webhook(payload, headers)
    result = await billing.handle_dodo_event(db, event, headers["webhook-id"])
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
    if wa.WhatsAppClient().enabled and get_settings().is_production:
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
async def admin_metrics(_: AdminUser, db: DB, days: int = 30):
    return await admin_svc.metrics(db, min(days, 365))


@router.get("/admin/ai-costs", tags=["admin"])
async def admin_ai_costs(_: AdminUser, db: DB, days: int = 30):
    return await admin_svc.ai_costs(db, min(days, 365))


@router.get("/admin/users", tags=["admin"])
async def admin_users(_: AdminUser, db: DB, q: str | None = None, limit: int = 50, offset: int = 0):
    query = select(User)
    if q:
        query = query.where(User.email.ilike(f"%{q}%") | User.name.ilike(f"%{q}%"))
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.order_by(User.created_at.desc()).limit(min(limit, 200)).offset(offset))
            ).scalars().all()
    items = []
    for u in rows:
        plan, sub = await usage.get_plan(db, u)
        items.append({"id": str(u.id), "email": u.email, "name": u.name, "role": u.role, "status": u.status,
                      "plan": plan.code, "created_at": u.created_at.isoformat(),
                      "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None})
    return {"items": items, "total": total}


@router.get("/admin/users/{user_id}", tags=["admin"])
async def admin_user(user_id: uuid.UUID, _: AdminUser, db: DB):
    u = await db.get(User, user_id)
    if u is None:
        raise NotFound("User")
    projects = (await db.execute(select(Course).where(Course.owner_id == u.id).order_by(Course.created_at.desc())
                                 .limit(50))).scalars().all()
    jobs = (await db.execute(select(GenerationJob).where(GenerationJob.owner_id == u.id)
                             .order_by(GenerationJob.created_at.desc()).limit(20))).scalars().all()
    return {"user": {"id": str(u.id), "email": u.email, "name": u.name, "role": u.role, "status": u.status,
                     "created_at": u.created_at.isoformat()},
            "usage": await usage.summary(db, u),
            "projects": [{"id": str(c.project_id), "topic": c.topic, "grade": c.grade, "status": c.status,
                          "created_at": c.created_at.isoformat()} for c in projects],
            "jobs": [{"id": str(j.id), "type": j.type, "status": j.status, "error": j.error,
                      "cost_usd": j.cost_usd, "created_at": j.created_at.isoformat()} for j in jobs]}


class AdminUserPatch(BaseModel):
    status: str | None = Field(None, pattern="^(active|suspended)$")
    role: str | None = Field(None, pattern="^(teacher|admin)$")
    plan: str | None = None
    months: int = Field(1, ge=1, le=36)
    credits_grant: int | None = Field(None, ge=1, le=100000)


@router.patch("/admin/users/{user_id}", tags=["admin"])
async def admin_patch_user(user_id: uuid.UUID, data: AdminUserPatch, admin: AdminUser, db: DB):
    u = await db.get(User, user_id)
    if u is None:
        raise NotFound("User")
    changes: dict[str, Any] = {}
    if data.status:
        u.status = changes["status"] = data.status
    if data.role:
        u.role = changes["role"] = data.role
    if data.credits_grant:
        await usage.refund(db, u.id, data.credits_grant, "admin_grant", str(admin.id))
        changes["credits_grant"] = data.credits_grant
    db.add(AuditLog(actor_id=admin.id, action="admin_update_user", target=str(u.id), details=changes))
    await db.commit()
    if data.plan:
        if await db.get(Plan, data.plan) is None:
            raise AppError("bad_request", "Unknown plan", 400)
        await billing.set_manual_plan(db, u.id, data.plan, months=data.months)
    return {"ok": True}


@router.get("/admin/plans", tags=["admin"])
async def admin_plans(_: AdminUser, db: DB):
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
async def admin_update_plan(code: str, data: PlanPatch, admin: AdminUser, db: DB):
    p = await db.get(Plan, code)
    if p is None:
        raise NotFound("Plan")
    for k, v in data.model_dump(exclude_none=True).items():
        if k == "limits":
            v = {**p.limits, **v}
        setattr(p, k, v)
    db.add(AuditLog(actor_id=admin.id, action="admin_update_plan", target=code, details=data.model_dump(
        exclude_none=True)))
    await db.commit()
    return plan_out(p)


@router.get("/admin/settings", tags=["admin"])
async def admin_settings(_: AdminUser):
    return await get_app_settings()


def _validate_setting(key: str, value: dict[str, Any]) -> None:
    """Reject admin edits that would break checkout or the media studio."""

    def bad(msg: str) -> AppError:
        return AppError("invalid_setting", msg, 422)

    if key == "billing":
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
    elif key == "ui" and value.get("default_skin", "classic") not in ("classic", "forest"):
        raise bad("Theme must be classic or forest.")


@router.put("/admin/settings/{key}", tags=["admin"])
async def admin_set_setting(key: str, value: dict[str, Any], admin: AdminUser, db: DB):
    if key not in DEFAULTS:
        raise AppError("bad_request", "Unknown setting", 400)
    _validate_setting(key, value)
    await set_setting(key, value)
    db.add(AuditLog(actor_id=admin.id, action="admin_update_setting", target=key, details=value))
    await db.commit()
    get_ai()._overrides_at = 0  # refresh model routing immediately
    return (await get_app_settings([key]))[key]


@router.get("/admin/jobs", tags=["admin"])
async def admin_jobs(_: AdminUser, db: DB, status: str | None = "failed", limit: int = 50):
    q = select(GenerationJob)
    if status:
        q = q.where(GenerationJob.status == status)
    rows = (await db.execute(q.order_by(GenerationJob.created_at.desc()).limit(min(limit, 200)))).scalars().all()
    return {"items": [{"id": str(j.id), "type": j.type, "status": j.status, "error": j.error, "attempts": j.attempts,
                       "owner_id": str(j.owner_id) if j.owner_id else None, "created_at": j.created_at.isoformat()}
                      for j in rows]}


@router.post("/admin/jobs/{job_id}/retry", tags=["admin"])
async def admin_retry(job_id: uuid.UUID, _: AdminUser, db: DB):
    j = await db.get(GenerationJob, job_id)
    if j is None:
        raise NotFound("Job")
    j.status, j.stage, j.error, j.attempts = "queued", "Queued (retry)", None, 0
    await db.commit()
    await run_inline_if_configured([j.id])
    return {"ok": True}


@router.get("/admin/subscriptions", tags=["admin"])
async def admin_subscriptions(_: AdminUser, db: DB):
    rows = (await db.execute(select(Subscription, User.email).join(User, User.id == Subscription.user_id)
                             .order_by(Subscription.created_at.desc()).limit(200))).all()
    return {"items": [{"email": e, "plan": s.plan_code, "status": s.status, "interval": s.interval,
                       "provider": s.provider, "period_end": s.current_period_end.isoformat()
                       if s.current_period_end else None} for s, e in rows]}
