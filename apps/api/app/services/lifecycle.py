"""Account deletion, data retention and periodic housekeeping (run by the worker's scheduler).

Deleting an account is a two-step process: the teacher (or staff) requests it, the account is locked and signed out
at once, and after the grace period the content is removed and the user row anonymised. Evidence the business must
keep (payments, subscriptions, credit ledger, consents, audit log, security events, AI cost records) stays, linked
to the anonymised row, so accounting and legal records remain intact.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sessionmaker, utcnow
from app.core.logging import log
from app.models import (
    AIUsage,
    AnalyticsEvent,
    ApiRequest,
    Base,
    EmailOutbox,
    IdempotencyKey,
    Notification,
    SecurityEvent,
    UploadedFile,
    User,
)
from app.services.settings import get_setting

logger = logging.getLogger("lifecycle")

DELETION_GRACE_DAYS = 30

# Tables kept after deletion (billing law, legal evidence, security and cost accounting).
KEEP_TABLES = {"users", "payments", "subscriptions", "credit_ledger", "consents", "audit_logs", "security_events",
               "ai_usage", "trial_grants", "api_requests", "analytics_events", "webhook_events", "email_outbox",
               "legal_documents", "announcements", "plans"}


async def request_deletion(db: AsyncSession, user: User, *, by: uuid.UUID | None, request=None) -> dict[str, Any]:
    """Lock the account now and schedule the purge. Cancels a paid subscription at period end."""
    from app.services import billing, sessions, usage
    from app.services.events import audit, security_event
    from app.services.notify import queue_email

    sub = await usage.active_subscription(db, user.id)
    if sub and sub.provider in ("stripe", "dodo") and not sub.cancel_at_period_end:
        try:
            await billing.cancel_subscription(db, user)
        except Exception as e:  # noqa: BLE001 - the deletion must still go ahead; staff see the audit entry
            log(logger, logging.ERROR, "deletion_cancel_failed", error=str(e)[:200])
    before = {"status": user.status}
    user.status = "pending_deletion"
    user.deletion_requested_at = utcnow()
    await sessions.revoke(db, user.id, reason="deletion")
    purge_on = user.deletion_requested_at + timedelta(days=DELETION_GRACE_DAYS)
    security_event(db, "deletion_requested", user_id=user.id, request=request, by=str(by) if by else "self")
    audit(db, by or user.id, "user.deletion_requested", request=request, target_user=user.id, target_type="user",
          target_id=str(user.id), before=before, after={"status": user.status, "purge_on": purge_on.isoformat()})
    queue_email(db, user, "deletion_scheduled", date=purge_on.strftime("%d %B %Y"))
    return {"status": user.status, "purge_on": purge_on.isoformat()}


def _user_fk_columns() -> list[tuple[Any, Any, bool]]:
    """(table, column, owned) for columns that reference users.id, children before parents. `owned` columns mean
    the row belongs to the user (deleted); SET NULL columns only mention them (e.g. a ticket's assignee)."""
    out = []
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in KEEP_TABLES:
            continue
        for col in table.columns:
            fks = [fk for fk in col.foreign_keys if fk.target_fullname == "users.id"]
            if fks:
                out.append((table, col, (fks[0].ondelete or "").upper() != "SET NULL"))
    return out


async def purge_account(db: AsyncSession, user: User) -> None:
    """Remove the teacher's content and personal data; keep anonymised records the business must retain."""
    from app.core.storage import get_storage
    from app.models import RewardSubmission

    storage = get_storage()
    # Preserve hashed reward claims and approved totals for abuse/budget checks,
    # but erase submitted free text once the person's account is purged.
    await db.execute(update(RewardSubmission).where(RewardSubmission.user_id == user.id)
                     .values(proof="", review_note=None))
    for f in (await db.execute(select(UploadedFile).where(UploadedFile.owner_id == user.id))).scalars().all():
        try:
            await storage.delete(f.storage_key)
        except Exception as e:  # noqa: BLE001 - a missing object must not block the purge
            log(logger, logging.WARNING, "purge_storage_error", error=str(e)[:200])
    for table, col, owned in _user_fk_columns():
        if owned:
            await db.execute(delete(table).where(col == user.id))
        else:
            await db.execute(update(table).where(col == user.id).values({col.name: None}))
    # Records we keep lose their link to the person where it isn't needed.
    await db.execute(update(AnalyticsEvent).where(AnalyticsEvent.user_id == user.id).values(user_id=None))
    await db.execute(update(ApiRequest).where(ApiRequest.user_id == user.id).values(user_id=None, ip=None,
                                                                                 user_agent=None))
    await db.execute(update(AIUsage).where(AIUsage.owner_id == user.id).values(owner_id=None))
    await db.execute(update(EmailOutbox).where(EmailOutbox.user_id == user.id).values(user_id=None,
                                                                                   to_email="deleted",
                                                                                   body_text=""))
    user.email = f"deleted-{user.id.hex}@deleted.invalid"
    user.name = ""
    user.password_hash = None
    user.phone = None
    user.avatar_url = None
    user.signup_meta = {}
    user.referral_code = None
    user.status = "deleted"
    user.deleted_at = utcnow()


async def purge_due_accounts() -> int:
    cutoff = utcnow() - timedelta(days=DELETION_GRACE_DAYS)
    done = 0
    async with get_sessionmaker()() as db:
        ids = (await db.execute(select(User.id).where(User.status == "pending_deletion",
                                                      User.deletion_requested_at <= cutoff).limit(20))).scalars().all()
    for uid in ids:
        async with get_sessionmaker()() as db:
            user = await db.get(User, uid)
            if user is None or user.status != "pending_deletion":
                continue
            from app.services.events import audit

            await purge_account(db, user)
            audit(db, None, "user.purged", target_user=user.id, target_type="user", target_id=str(user.id))
            await db.commit()
            done += 1
    return done


async def retention_cleanup() -> dict[str, int]:
    """Delete operational logs past their retention period (admin-configurable in settings.system)."""
    days = {"api_requests": 90, "security_events": 365, "analytics_events": 400, "notifications": 180,
            "email_outbox": 90, **((await get_setting("system")).get("retention_days") or {})}
    now = utcnow()
    out: dict[str, int] = {}
    async with get_sessionmaker()() as db:
        for name, model, extra in (
            ("api_requests", ApiRequest, None),
            ("security_events", SecurityEvent, None),
            ("analytics_events", AnalyticsEvent, None),
            ("notifications", Notification, Notification.read_at.is_not(None)),
            ("email_outbox", EmailOutbox, EmailOutbox.status.in_(("sent", "logged", "failed"))),
        ):
            q = delete(model).where(model.created_at < now - timedelta(days=int(days[name])))
            if extra is not None:
                q = q.where(extra)
            out[name] = (await db.execute(q)).rowcount or 0
        out["idempotency_keys"] = (await db.execute(delete(IdempotencyKey).where(
            IdempotencyKey.created_at < now - timedelta(hours=24)))).rowcount or 0
        await db.commit()
    return out
