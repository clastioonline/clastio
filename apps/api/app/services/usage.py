"""Plans, credits and usage limits. Every limit lives in the `plans` table (admin-editable)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import LimitExceeded
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
    return plan, sub


async def used(db: AsyncSession, user_id: uuid.UUID, resource: str, since: datetime) -> int:
    total = (await db.execute(select(func.coalesce(func.sum(CreditLedger.amount), 0)).where(
        CreditLedger.owner_id == user_id, CreditLedger.resource == resource,
        CreditLedger.created_at >= since))).scalar_one()
    return int(-total)


async def credit_cost(kind: str, quantity: int = 1) -> int:
    costs = await get_setting("credit_costs")
    return int(costs.get(kind, 1)) * quantity


async def check(db: AsyncSession, user: User, resource: str, amount: int) -> None:
    if user.role == "admin":
        return
    plan, sub = await get_plan(db, user)
    limit = plan.limits.get(resource if resource != "credits" else "credits")
    if limit is None or limit == -1:
        return
    spent = await used(db, user.id, resource, period_start(sub))
    if spent + amount > int(limit):
        raise LimitExceeded(
            f"This needs {amount} {resource.replace('_', ' ')} but only {max(0, int(limit) - spent)} are left on "
            f"your {plan.name} plan this month.",
            {"resource": resource, "limit": limit, "used": spent, "needed": amount, "plan": plan.code})


async def consume(db: AsyncSession, user_id: uuid.UUID, amount: int, reason: str, ref: str | None = None,
                  resource: str = "credits") -> None:
    if amount:
        db.add(CreditLedger(owner_id=user_id, amount=-abs(amount), resource=resource, reason=reason, ref=ref))


async def refund(db: AsyncSession, user_id: uuid.UUID, amount: int, reason: str, ref: str | None = None,
                 resource: str = "credits") -> None:
    if amount:
        db.add(CreditLedger(owner_id=user_id, amount=abs(amount), resource=resource, reason=reason, ref=ref))


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
        out["trial"] = {"active": True, "ends_at": sub.current_period_end.isoformat(), "days_left": max(0, round(left))}
    elif had_trial and (sub is None or sub.provider in ("trial", "manual")) and plan.code == "free":
        out["trial"] = {"active": False, "ended": True}
    if sub:
        out["subscription"] = {"status": sub.status, "interval": sub.interval,
                               "current_period_end": sub.current_period_end.isoformat()
                               if sub.current_period_end else None,
                               "cancel_at_period_end": sub.cancel_at_period_end, "provider": sub.provider}
    for res in ("credits", "ai_images", "whatsapp_messages"):
        out["usage"][res] = {"used": await used(db, user.id, res, since), "limit": plan.limits.get(res)}
    storage = (await db.execute(select(func.coalesce(func.sum(UploadedFile.size_bytes), 0)).where(
        UploadedFile.owner_id == user.id))).scalar_one()
    out["usage"]["storage_mb"] = {"used": round(storage / 1_048_576, 1), "limit": plan.limits.get("storage_mb")}
    ai_cost = (await db.execute(select(func.coalesce(func.sum(AIUsage.cost_usd), 0)).where(
        AIUsage.owner_id == user.id, AIUsage.created_at >= since))).scalar_one()
    out["ai_cost_usd"] = round(float(ai_cost), 4)
    return out
