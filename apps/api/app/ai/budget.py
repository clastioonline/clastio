"""Atomic paid-call admission. Unknown charges remain held until invoice reconciliation.

This ledger starts at deployment. Rates/ceilings must cover the configured provider's
context, media and cache-write pricing; it is not a replacement for provider invoices.
"""
from __future__ import annotations

import calendar
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Integer, and_, case, cast, func, or_, select, text

from app.ai.base import AIError, Usage
from app.core.db import get_sessionmaker
from app.core.logging import job_id_var
from app.models import AICallReservation, AppSetting, GenerationJob


class BudgetError(AIError):
    def __init__(self, message: str):
        super().__init__(message, retryable=False)


class BudgetPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    live_enabled: bool = False
    daily_usd: float = Field(10, ge=0, le=100000)
    monthly_usd: float = Field(100, ge=0, le=1000000)
    user_monthly_usd: float = Field(5, ge=0, le=100000)
    job_usd: float = Field(2, ge=0, le=10000)
    call_usd: float = Field(1, ge=0, le=1000)
    max_calls_per_job: int = Field(60, ge=1, le=1000)
    max_input_bytes: int = Field(120000, ge=1, le=1000000)
    max_output_tokens: int = Field(24000, ge=1, le=32000)


class RateCard(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    input: float = Field(ge=0, le=10000)
    output: float = Field(ge=0, le=10000)
    cached: float = Field(ge=0, le=10000)
    cache_write: float = Field(ge=0, le=10000)
    # Conservative upper bound for one call at the enforced input/output limits.
    # Includes media, reasoning and long-context premiums. Never supplied by users.
    ceiling_usd: float = Field(gt=0, le=1000)
    source: str = Field(min_length=8, max_length=500)


async def lock(db):
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('ai-budget', 0))"))


async def config(db):
    rows = (await db.execute(select(AppSetting).where(
        AppSetting.key.in_(["ai_budget", "ai_rate_cards"])))).scalars().all()
    settings = {r.key: r.value for r in rows}
    return BudgetPolicy.model_validate(settings.get("ai_budget", {})), settings.get("ai_rate_cards", {})


def job_context(job_id):
    return job_id or (uuid.UUID(job_id_var.get()) if job_id_var.get() else None)


async def reserve(*, provider, model, task, owner_id, job_id, input_bytes=0, output_tokens=0):
    if provider == "offline":
        return None
    job_id = job_context(job_id)
    async with get_sessionmaker()() as db:
        await lock(db)
        policy, cards = await config(db)
        if not policy.live_enabled:
            raise BudgetError("Live AI is paused. Saved resources remain available; contact your administrator.")
        card_data = cards.get(f"{provider}:{model}")
        if not card_data:
            raise BudgetError("This AI model needs an approved price card before it can be used.")
        card = RateCard.model_validate(card_data)
        if input_bytes > policy.max_input_bytes or output_tokens > policy.max_output_tokens:
            raise BudgetError("This request is too large. Split the material into smaller sections.")
        job = None
        if job_id:
            job = await db.get(GenerationJob, job_id)
            if job:
                owner_id = owner_id or job.owner_id
        amount = Decimal(str(card.ceiling_usd))
        now = datetime.now(UTC)
        month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        unresolved = AICallReservation.status.in_(["pending", "uncertain"])
        exposure = func.coalesce(AICallReservation.charged_usd, AICallReservation.reserved_usd)

        async def check(cap, *conditions):
            spent = await db.scalar(select(func.coalesce(func.sum(exposure), 0)).where(*conditions))
            if spent + amount > Decimal(str(cap)):
                raise BudgetError("AI spending allowance reached. Saved work is available; try after reset or contact support.")

        if amount > Decimal(str(policy.call_usd)):
            raise BudgetError("This model's call allowance exceeds the configured spending limit.")
        await check(policy.daily_usd, or_(AICallReservation.created_at >= day, unresolved))
        await check(policy.monthly_usd, or_(AICallReservation.created_at >= month, unresolved))
        # Anonymous/internal calls share a user budget rather than bypassing it.
        await check(policy.user_monthly_usd, AICallReservation.owner_id == owner_id,
                    or_(AICallReservation.created_at >= month, unresolved))
        if job_id:
            await check(policy.job_usd, AICallReservation.job_id == job_id)
            count = await db.scalar(select(func.count()).select_from(AICallReservation).where(
                AICallReservation.job_id == job_id))
            if count >= policy.max_calls_per_job:
                raise BudgetError("This job reached its AI call limit. Contact support before retrying.")
            uncertain = await db.scalar(select(func.count()).select_from(AICallReservation).where(
                AICallReservation.job_id == job_id, or_(AICallReservation.status == "uncertain",
                    and_(AICallReservation.status == "pending", AICallReservation.created_at < job.started_at)
                    if job and job.started_at else False)))
            if uncertain:
                raise BudgetError("A previous call has an unconfirmed charge. Support must reconcile it before retrying.")
        row = AICallReservation(owner_id=owner_id, job_id=job_id, provider=provider, model=model,
                                task=task, reserved_usd=amount, rates=card.model_dump())
        db.add(row)
        await db.commit()
        return row.id


def price(rates, usage):
    total = sum(Decimal(str(rates[key])) * count for key, count in (
        ("input", usage.input_tokens), ("output", usage.output_tokens),
        ("cached", usage.cached_tokens), ("cache_write", usage.cache_write_tokens))) / 1000000
    return total.quantize(Decimal("0.00000001"))


async def settle(ticket, usage: Usage | None, success: bool):
    if ticket is None:
        return None
    async with get_sessionmaker()() as db:
        await lock(db)
        row = await db.get(AICallReservation, ticket, with_for_update=True)
        if row.status != "pending":
            return float(row.charged_usd or row.reserved_usd)
        row.usage = asdict(usage) if usage else {}
        row.success = success
        # Media and missing metadata cannot be accurately priced with a token rate card.
        known = usage is not None and usage.reported and not usage.images and not usage.video_seconds
        row.status = "settled" if known else "uncertain"
        row.charged_usd = price(row.rates, usage) if known else None
        if known and row.charged_usd > row.reserved_usd:
            # A bad rate ceiling is a configuration incident: account honestly and stop all new calls.
            setting = await db.get(AppSetting, "ai_budget")
            policy, _ = await config(db)
            policy.live_enabled = False
            if setting:
                setting.value = policy.model_dump()
            else:
                db.add(AppSetting(key="ai_budget", value=policy.model_dump()))
            row.note = "Actual cost exceeded approved ceiling; live AI automatically paused."
        await db.commit()
        return float(row.charged_usd if known else row.reserved_usd)


async def dashboard(db):
    policy, cards = await config(db)
    now = datetime.now(UTC)
    month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    scope = or_(AICallReservation.created_at >= month, AICallReservation.status.in_(["pending", "uncertain"]))
    spent, held, failed = (await db.execute(select(
        func.coalesce(func.sum(AICallReservation.charged_usd), 0),
        func.coalesce(func.sum(case((AICallReservation.charged_usd.is_(None),
                                    AICallReservation.reserved_usd), else_=0)), 0),
        func.coalesce(func.sum(case((AICallReservation.success.is_(False),
                                    AICallReservation.charged_usd), else_=0)), 0)).where(scope))).one()
    spent, held, failed = float(spent), float(held), float(failed)
    rows = (await db.execute(select(AICallReservation).where(scope, AICallReservation.charged_usd.is_(None))
        .order_by(AICallReservation.created_at.desc()).limit(100))).scalars().all()
    token_fields = ["input_tokens", "output_tokens", "cached_tokens", "cache_write_tokens", "reasoning_tokens"]
    tokens = (await db.execute(select(*[func.coalesce(func.sum(cast(
        AICallReservation.usage[field].astext, Integer)), 0) for field in token_fields]).where(scope))).one()
    return {"policy": policy.model_dump(), "rate_cards": cards, "spent_usd": spent, "held_usd": held,
            "remaining_usd": max(0, policy.monthly_usd - spent - held),
            "failed_cost_usd": failed, "tokens": dict(zip(token_fields, tokens, strict=True)),
            "forecast_usd": spent / max(1, now.day) * calendar.monthrange(now.year, now.month)[1],
            "alert": "limit" if spent + held >= policy.monthly_usd else
                     "warning" if spent + held >= policy.monthly_usd * .8 else "normal",
            "unresolved": [{"id": str(r.id), "provider": r.provider, "model": r.model,
                "status": r.status, "reserved_usd": float(r.reserved_usd), "job_id": str(r.job_id) if r.job_id else None,
                "created_at": r.created_at.isoformat()} for r in rows if r.charged_usd is None][:100]}
