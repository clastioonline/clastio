"""Plans, credits and usage limits. Every limit lives in the `plans` table (admin-editable)."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, LimitExceeded
from app.models import (
    AIUsage,
    ClassSection,
    CreditLedger,
    Plan,
    StyleProfile,
    Subscription,
    UploadedFile,
    User,
)
from app.services.settings import get_setting

ACTIVE_STATUSES = ("active", "trialing", "past_due")

DEFAULT_PLANS: list[dict[str, Any]] = [
    {"code": "free", "name": "Free", "price_monthly_aed": 0, "price_annual_aed": 0, "sort": 0,
     "limits": {"credits": 60, "style_profiles": 1, "classes": 2, "ai_images": 0, "whatsapp_messages": 0,
                "storage_mb": 200, "max_lectures": 3},
     "features": ["2 short lesson decks a month", "1 teacher style", "Worksheets & quizzes (limited)"]},
    {"code": "teacher", "name": "Teacher", "price_monthly_aed": 99, "price_annual_aed": 990, "sort": 1,
     "limits": {"credits": 800, "style_profiles": 2, "classes": 6, "ai_images": 30, "whatsapp_messages": 0,
                "storage_mb": 2000, "max_lectures": 10},
     "features": ["~20 full lesson decks a month", "Teacher memory", "Lesson planning", "Worksheets", "Quizzes",
                  "Homework"]},
    {"code": "pro", "name": "Teacher Pro", "price_monthly_aed": 149, "price_annual_aed": 1490, "sort": 2,
     "limits": {"credits": 2000, "style_profiles": 5, "classes": -1, "ai_images": 100, "whatsapp_messages": 0,
                "storage_mb": 5000, "max_lectures": 20},
     "features": ["Higher limits", "Unlimited classes & subjects", "Advanced memory & reflections",
                  "Arabic / bilingual slides", "Exports to Forms & LMS"]},
    {"code": "assistant", "name": "Genie Assistant", "price_monthly_aed": 249, "price_annual_aed": 2490,
     "sort": 3,
     "limits": {"credits": 4000, "style_profiles": 10, "classes": -1, "ai_images": 200, "whatsapp_messages": 300,
                "storage_mb": 10000, "max_lectures": 30, "daily_planning": True},
     "features": ["Everything in Pro", "Daily & weekly planning", "WhatsApp assistant", "Cover lessons",
                  "Assessments", "Priority generation"]},
]


def period_start(sub: Subscription | None) -> datetime:
    if sub and sub.current_period_start:
        return sub.current_period_start
    now = datetime.now(UTC)
    return datetime(now.year, now.month, 1, tzinfo=UTC)


# Trials and admin-granted plans end on their end date; gateway subscriptions end by webhook.
SELF_EXPIRING = ("trial", "manual")


async def active_subscription(db: AsyncSession, user_id: uuid.UUID) -> Subscription | None:
    return (await db.execute(
        select(Subscription).where(
            Subscription.user_id == user_id, Subscription.status.in_(ACTIVE_STATUSES),
            or_(Subscription.provider.notin_(SELF_EXPIRING), Subscription.current_period_end.is_(None),
                Subscription.current_period_end > func.now()))
        .order_by(Subscription.created_at.desc()))).scalars().first()


async def start_trial(db: AsyncSession, user: User) -> Subscription | None:
    """Give a new teacher the admin-configured free trial (no card). Returns None when trials are off."""
    from app.core.db import utcnow

    cfg = await get_setting("trial")
    if not cfg.get("enabled") or user.role == "admin" or int(cfg.get("days", 0)) <= 0:
        return None
    now = utcnow()
    sub = Subscription(user_id=user.id, plan_code=cfg.get("plan", "pro"), status="trialing", provider="trial",
                       interval="month", current_period_start=now,
                       current_period_end=now + timedelta(days=int(cfg["days"])))
    db.add(sub)
    return sub


async def get_plan(db: AsyncSession, user: User) -> tuple[Plan, Subscription | None]:
    sub = await active_subscription(db, user.id)
    code = sub.plan_code if sub else "free"
    plan = await db.get(Plan, code) or await db.get(Plan, "free")
    if plan is None:  # plans not seeded yet (fresh DB)
        d = DEFAULT_PLANS[0]
        plan = Plan(code=d["code"], name=d["name"], limits=d["limits"], features=d["features"])
    if sub and sub.provider == "trial":
        cfg = await get_setting("trial")
        limits = dict(plan.limits)
        for resource in ("credits", "ai_images", "whatsapp_messages"):
            cap = int(cfg.get(resource, limits.get(resource, 0)))
            original = limits.get(resource)
            limits[resource] = cap if original in (None, -1) else min(cap, original)
        # A detached view: never mutate the paid plan's persisted limits.
        plan = Plan(code=plan.code, name=plan.name, limits=limits, features=plan.features,
                    price_monthly_aed=plan.price_monthly_aed, price_annual_aed=plan.price_annual_aed)
    return plan, sub


async def used(db: AsyncSession, user_id: uuid.UUID, resource: str, since: datetime) -> int:
    total = (await db.execute(select(func.coalesce(func.sum(CreditLedger.amount), 0)).where(
        CreditLedger.owner_id == user_id, CreditLedger.resource == resource,
        CreditLedger.created_at >= since))).scalar_one()
    return int(-total)


async def credit_cost(kind: str, quantity: int = 1) -> int:
    costs = await get_setting("credit_costs")
    return int(costs.get(kind, 1)) * quantity


GENERATION_JOB_TYPES = ("course_plan", "lesson_generation", "slide_regeneration", "document_generation",
                        "media_generation", "assistant_reply", "image_replacement")


async def plan_limits(db: AsyncSession, user: User) -> dict[str, Any]:
    """Runtime limits for the user's plan from the admin-editable `plan_limits` setting ("*" is the fallback)."""
    plan, _ = await get_plan(db, user)
    cfg = await get_setting("plan_limits")
    return {**(cfg.get("*") or {}), **(cfg.get(plan.code) or {})}


async def lock_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Serialise credit checks for one user until the caller's transaction ends (commit or rollback)."""
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"credits:{user_id}"})


async def reserved(db: AsyncSession, user_id: uuid.UUID) -> int:
    from app.models import GenerationJob

    return int((await db.execute(select(func.coalesce(func.sum(GenerationJob.credits_reserved), 0)).where(
        GenerationJob.owner_id == user_id, GenerationJob.status.in_(("queued", "running"))))).scalar_one())


async def check_generation_allowed(db: AsyncSession, user: User, jobs: int = 1) -> None:
    """Platform switches and per-plan daily volume. Staff are exempt from plan limits, not from the kill switch."""
    from app.models import GenerationJob

    system = await get_setting("system")
    if not system.get("ai_generation_enabled", True):
        raise AppError("ai_paused", "AI generation is paused for maintenance. Please try again shortly.", 503)
    if system.get("require_email_verification_for_generation") and not user.email_verified and user.role != "admin":
        raise AppError("email_unverified", "Please confirm your email address before generating content.", 403)
    if user.role == "admin" or jobs <= 0:
        return
    daily = (await plan_limits(db, user)).get("daily_generations")
    if daily is None or daily < 0:
        return
    since = datetime.now(UTC) - timedelta(hours=24)
    today = (await db.execute(select(func.count()).select_from(GenerationJob).where(
        GenerationJob.owner_id == user.id, GenerationJob.type.in_(GENERATION_JOB_TYPES),
        GenerationJob.created_at >= since))).scalar_one()
    if today + jobs > int(daily):
        plan, _ = await get_plan(db, user)
        raise LimitExceeded(
            f"Your {plan.name} plan allows {daily} generations a day. You can generate more tomorrow, or upgrade "
            f"for a higher daily limit.", {"resource": "daily_generations", "limit": daily, "used": today,
                                           "needed": jobs, "plan": plan.code})


async def check(db: AsyncSession, user: User, resource: str, amount: int, *, jobs: int = 0) -> None:
    """Server-side limit check. Takes a per-user lock held until the caller commits, and counts credits already
    reserved by queued/running jobs, so two simultaneous requests can't both spend the last credits. Callers
    enqueue with credits_reserved=<cost> in the same transaction."""
    if resource == "credits":
        await check_generation_allowed(db, user, jobs)
    if user.role == "admin":
        return
    plan, sub = await get_plan(db, user)
    limit = plan.limits.get(resource if resource != "credits" else "credits")
    if limit is None or limit == -1:
        return
    await lock_user(db, user.id)
    spent = await used(db, user.id, resource, period_start(sub))
    held = await reserved(db, user.id) if resource == "credits" else 0
    if spent + held + amount > int(limit):
        left = max(0, int(limit) - spent - held)
        raise LimitExceeded(
            f"This needs {amount} {resource.replace('_', ' ')} but only {left} are left on "
            f"your {plan.name} {'trial' if sub and sub.provider == 'trial' else 'plan this month'}" + (" (some are held by lessons still generating)." if held else "."),
            {"resource": resource, "limit": limit, "used": spent, "reserved": held, "needed": amount,
             "plan": plan.code})


def ledger_event_type(reason: str, amount: int) -> str:
    """Classify a ledger row: CREDIT_USAGE | CREDIT_REFUND | CREDIT_PURCHASE | CREDIT_ADMIN_GRANT |
    CREDIT_ADJUSTMENT | CREDIT_EXPIRATION."""
    if reason.startswith("admin_"):
        return "CREDIT_ADMIN_GRANT" if amount > 0 else "CREDIT_ADJUSTMENT"
    if reason.startswith("media_pack:") or reason.startswith("purchase"):
        return "CREDIT_PURCHASE"
    if "refund" in reason:
        return "CREDIT_REFUND"
    if reason.startswith("expire"):
        return "CREDIT_EXPIRATION"
    if reason == "monthly_allowance":
        return "CREDIT_ADJUSTMENT"
    return "CREDIT_USAGE" if amount < 0 else "CREDIT_ADJUSTMENT"


def ledger_entry(user_id: uuid.UUID, amount: int, reason: str, *, ref: str | None = None, resource: str = "credits",
                 event_type: str | None = None, actor_id: uuid.UUID | None = None, resource_type: str | None = None,
                 resource_id: str | None = None, provider_cost_usd: float | None = None,
                 meta: dict[str, Any] | None = None) -> CreditLedger:
    """Build a ledger row. Every credit movement goes through here so rows are typed and traceable."""
    from app.core.logging import request_id_var

    return CreditLedger(owner_id=user_id, amount=amount, resource=resource, reason=reason[:80], ref=ref,
                        event_type=event_type or ledger_event_type(reason, amount), actor_id=actor_id,
                        resource_type=resource_type, resource_id=resource_id, provider_cost_usd=provider_cost_usd,
                        request_id=request_id_var.get(), meta=meta or {})


async def consume(db: AsyncSession, user_id: uuid.UUID, amount: int, reason: str, ref: str | None = None,
                  resource: str = "credits", **extra: Any) -> None:
    if amount:
        db.add(ledger_entry(user_id, -abs(amount), reason, ref=ref, resource=resource, **extra))
        from app.services.events import track

        track(db, USAGE_EVENTS.get(reason, "document_generated" if resource == "credits" else "credits_used"),
              user_id=user_id, reason=reason, resource=resource, amount=abs(amount))
        if resource == "credits":
            await warn_usage(db, user_id, resource)


# Product analytics event recorded for each kind of credit spend.
USAGE_EVENTS = {"course_plan": "course_planned", "lesson_generation": "lesson_generated",
                "slide_regeneration": "slide_regenerated", "ai_image": "ai_images_used",
                "media_image": "media_generated", "media_video": "media_generated"}
USAGE_THRESHOLDS = (50, 75, 90, 100)
EMAIL_THRESHOLDS = (90, 100)


async def warn_usage(db: AsyncSession, user_id: uuid.UUID, resource: str) -> int | None:
    """Tell the teacher when they cross 50/75/90/100% of this period's allowance. Each threshold is sent once per
    period (the notification's dedupe key); 90% and 100% also send an email."""
    from app.core.config import get_settings
    from app.services.notify import notify, queue_email

    user = await db.get(User, user_id)
    if user is None or user.role == "admin":
        return None
    plan, sub = await get_plan(db, user)
    limit = plan.limits.get(resource)
    if not limit or limit == -1:
        return None
    since = period_start(sub)
    spent = await used(db, user_id, resource, since)  # autoflush includes the row just added
    pct = spent * 100 // int(limit)
    crossed = [t for t in USAGE_THRESHOLDS if pct >= t]
    if not crossed:
        return None
    t = crossed[-1]
    key = f"usage:{resource}:{since.date().isoformat()}:{t}"
    trial = bool(sub and sub.provider == "trial")
    period_label = "trial" if trial else "this month"
    title = f"You've used all your {period_label} credits" if t >= 100 else f"You've used {t}% of your {period_label} credits"
    body = (f"Your {'trial' if trial else plan.name + ' plan'} includes {limit} credits {'for the entire trial' if trial else 'a month'}. "
            + (("Choose a plan to keep creating. Your existing work stays safe." if trial else
                "New lessons will wait until next month unless you upgrade.") if t >= 100 else
               f"{max(0, int(limit) - spent)} are left."))
    if await notify(db, user_id, "usage", title, body, "/billing", dedupe_key=key) and t in EMAIL_THRESHOLDS:
        queue_email(db, user, "usage_warning", link=f"{get_settings().public_web_url}/billing", percent=str(t),
                    plan=plan.name)
    return t


async def refund(db: AsyncSession, user_id: uuid.UUID, amount: int, reason: str, ref: str | None = None,
                 resource: str = "credits", **extra: Any) -> None:
    if amount:
        db.add(ledger_entry(user_id, abs(amount), reason, ref=ref, resource=resource, **extra))


async def adjust(db: AsyncSession, user_id: uuid.UUID, amount: int, *, resource: str, reason: str,
                 actor_id: uuid.UUID) -> CreditLedger:
    """Staff credit adjustment. Positive grants credits, negative removes them. A reason is mandatory."""
    row = ledger_entry(user_id, amount, "admin_grant" if amount > 0 else "admin_adjustment", resource=resource,
                       actor_id=actor_id, meta={"reason": reason})
    db.add(row)
    return row


async def check_storage(db: AsyncSession, user: User, adding_bytes: int) -> None:
    """Per-plan storage quota (limits.storage_mb), counted from the teacher's live uploads."""
    if user.role == "admin":
        return
    plan, _ = await get_plan(db, user)
    limit = plan.limits.get("storage_mb")
    if limit is None or limit == -1:
        return
    stored = (await db.execute(select(func.coalesce(func.sum(UploadedFile.size_bytes), 0)).where(
        UploadedFile.owner_id == user.id, UploadedFile.deleted_at.is_(None)))).scalar_one()
    if stored + adding_bytes > int(limit) * 1_048_576:
        raise LimitExceeded(f"Your {plan.name} plan includes {limit} MB of storage and this file would go over it. "
                            "Delete old uploads or upgrade.", {"resource": "storage_mb", "limit": limit,
                                                               "used": round(stored / 1_048_576, 1)})


async def check_count_limit(db: AsyncSession, user: User, key: str) -> None:
    if user.role == "admin":
        return
    plan, _ = await get_plan(db, user)
    limit = plan.limits.get(key)
    if limit is None or limit == -1:
        return
    model = {"style_profiles": StyleProfile, "classes": ClassSection}[key]
    owner_col = model.owner_id if hasattr(model, "owner_id") else model.user_id
    count = (await db.execute(select(func.count()).select_from(model).where(owner_col == user.id))).scalar_one()
    if count >= int(limit):
        raise LimitExceeded(f"Your {plan.name} plan allows {limit} {key.replace('_', ' ')}. Upgrade for more.",
                            {"resource": key, "limit": limit})


async def summary(db: AsyncSession, user: User) -> dict[str, Any]:
    plan, sub = await get_plan(db, user)
    since = period_start(sub)
    out: dict[str, Any] = {"plan": {"code": plan.code, "name": plan.name}, "period_start": since.isoformat(),
                           "subscription": None, "usage": {}}
    had_trial = (await db.execute(select(Subscription.id).where(Subscription.user_id == user.id,
                                                                Subscription.provider == "trial"))).first()
    out["trial"] = None
    if sub and sub.provider == "trial" and sub.current_period_end:
        left = (sub.current_period_end - datetime.now(UTC)).total_seconds() / 86400
        out["trial"] = {"active": True, "ends_at": sub.current_period_end.isoformat(), "days_left": max(0, math.ceil(left)), "limits": plan.limits}
    elif had_trial and (sub is None or sub.provider in ("trial", "manual")) and plan.code == "free":
        out["trial"] = {"active": False, "ended": True}
    if sub:
        out["subscription"] = {"status": sub.status, "interval": sub.interval,
                               "current_period_end": sub.current_period_end.isoformat()
                               if sub.current_period_end else None,
                               "cancel_at_period_end": sub.cancel_at_period_end, "provider": sub.provider}
    for res in ("credits", "ai_images", "whatsapp_messages"):
        out["usage"][res] = {"used": max(0, await used(db, user.id, res, since)), "limit": plan.limits.get(res)}
    storage = (await db.execute(select(func.coalesce(func.sum(UploadedFile.size_bytes), 0)).where(
        UploadedFile.owner_id == user.id))).scalar_one()
    out["usage"]["storage_mb"] = {"used": round(storage / 1_048_576, 1), "limit": plan.limits.get("storage_mb")}
    ai_cost = (await db.execute(select(func.coalesce(func.sum(AIUsage.cost_usd), 0)).where(
        AIUsage.owner_id == user.id, AIUsage.created_at >= since))).scalar_one()
    out["ai_cost_usd"] = round(float(ai_cost), 4)
    return out
