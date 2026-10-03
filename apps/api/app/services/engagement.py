"""Referral attribution, durable rewards, and a private progress summary."""
from __future__ import annotations

import secrets
from urllib.parse import urlencode

from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.models import CreditLedger, GenerationJob, User
from app.services.settings import get_setting
from app.services.usage import ledger_entry


async def attribute_referral(db, user: User, code: str | None) -> None:
    cfg = await get_setting("referrals")
    if not cfg.get("enabled") or not code or user.role == "admin" or user.referred_by_id:
        return
    referrer = (await db.execute(select(User).where(User.referral_code == code.strip().lower(),
                                                   User.status == "active", User.role == "teacher"))).scalars().first()
    if referrer and referrer.id != user.id:
        from app.api.routes.auth import normalised_email_hash
        if normalised_email_hash(user.email) != normalised_email_hash(referrer.email):
            user.referred_by_id = referrer.id


async def reward_referral(db, user_id) -> bool:
    """Called only for a signed gateway webhook confirming a positive subscription payment."""
    cfg = await get_setting("referrals")
    if not cfg.get("enabled"):
        return False
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                     {"key": f"referral:{user_id}"})
    user = await db.get(User, user_id)
    if not user or not user.referred_by_id or user.role == "admin" or user.status != "active" or not user.email_verified:
        return False
    referrer = await db.get(User, user.referred_by_id)
    if not referrer or referrer.id == user.id or referrer.status != "active" or referrer.role == "admin":
        return False
    ref = f"referral:{user.id}"
    if (await db.execute(select(CreditLedger.id).where(CreditLedger.ref == ref,
                                                      CreditLedger.reason == "referral_reward"))).first():
        return False
    amount = int(cfg.get("reward_media_credits", 25))
    if amount <= 0:
        return False
    for recipient in (referrer, user):
        db.add(ledger_entry(recipient.id, amount, "referral_reward", ref=ref, resource="media_credits",
                            meta={"referred_user_id": str(user.id)}))
        # Use the existing preference-aware event pipeline for optional reward emails.
        from app.services.notifications import send
        await send(db, recipient, "referral_reward", dedupe_key=f"{ref}:email:{recipient.id}", credits=amount)
    await db.flush()
    return True


async def referral_summary(db, user: User) -> dict:
    cfg = await get_setting("referrals")
    if not user.referral_code:
        # Existing accounts can also get an invite link; persist before returning it.
        await db.execute(select(User.id).where(User.id == user.id).with_for_update())
        await db.refresh(user)
        if not user.referral_code:
            user.referral_code = secrets.token_hex(8)
        await db.commit()
    invited = (await db.execute(select(func.count(User.id)).where(User.referred_by_id == user.id))).scalar_one()
    rewarded, credits = (await db.execute(select(func.count(CreditLedger.id), func.coalesce(func.sum(CreditLedger.amount), 0)).where(
        CreditLedger.owner_id == user.id, CreditLedger.reason == "referral_reward"))).one()
    completed = (await db.execute(select(func.count(GenerationJob.id)).where(
        GenerationJob.owner_id == user.id, GenerationJob.status == "succeeded"))).scalar_one()
    milestones = [1, 5, 10, 25, 50, 100]
    return {"enabled": bool(cfg.get("enabled")) and user.role != "admin", "code": user.referral_code,
            "url": f"{get_settings().public_web_url}/signup?{urlencode({'ref': user.referral_code})}",
            "reward_media_credits": int(cfg.get("reward_media_credits", 25)), "invited": invited,
            "qualified": rewarded, "earned_media_credits": int(credits),
            "progress": {"completed_tasks": completed, "next_milestone": next((n for n in milestones if n > completed), None)}}
