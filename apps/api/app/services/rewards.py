"""Reviewed Free-plan rewards. No completion event automatically awards credits."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, text

from app.core.db import utcnow
from app.core.errors import AppError
from app.models import AppSetting, RewardDeviceClaim, RewardSubmission, RewardTask, User
from app.services import billing, usage
from app.services.events import audit
from app.services.settings import DEFAULTS


async def program(db) -> dict:
    """Write decisions read the persisted row in the caller's transaction, never a process cache."""
    value = (await db.execute(select(AppSetting.value).where(AppSetting.key == "rewards"))).scalar_one_or_none()
    return {**DEFAULTS["rewards"], **(value or {})}


async def ineligible_reason(db, user: User) -> str | None:
    if user.role != "teacher":
        return "Rewards are for teachers on the Free plan."
    if not user.email_verified:
        return "Verify your email before submitting a task."
    if user.status != "active":
        return "Rewards require an active account."
    plan, sub = await usage.get_plan(db, user)
    if plan.code != "free" or sub:
        return "Rewards are available after your trial ends, while you use the Free plan."
    if await billing.pending_checkout(db, user.id, reconcile_expiry=True) or await billing.manageable_online_subscription(db, user.id):
        return "Finish or resolve your payment checkout before using Free-plan rewards."
    return None


def task_open(task: RewardTask, now: datetime) -> bool:
    return task.published and (task.starts_at is None or task.starts_at <= now) and (task.ends_at is None or task.ends_at > now)


def month_end(now: datetime) -> datetime:
    return datetime(now.year + (now.month == 12), 1 if now.month == 12 else now.month + 1, 1, tzinfo=UTC)


async def submit(db, user: User, task_id: uuid.UUID, proof: str, device_hash: str) -> RewardSubmission:
    from app.api.routes.auth import normalised_email_hash

    await billing.lock_plan_changes(db, user.id)
    if reason := await ineligible_reason(db, user):
        raise AppError("reward_ineligible", reason, 403)
    if not (await program(db)).get("enabled"):
        raise AppError("rewards_paused", "Tasks are not available yet. Your Free allowance remains available.", 409)
    task = await db.get(RewardTask, task_id)
    if not task or not task_open(task, utcnow()):
        raise AppError("reward_task_unavailable", "This task is unpublished, expired or not open yet.", 409)
    email_hash = normalised_email_hash(user.email)
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                     {"key": f"reward-task:{task_id}:{email_hash}"})
    previous = (await db.execute(select(RewardSubmission).where(
        RewardSubmission.task_id == task_id, RewardSubmission.email_hash == email_hash).with_for_update())).scalars().first()
    claimed = (await db.execute(select(RewardDeviceClaim.id).where(
        RewardDeviceClaim.task_id == task_id, RewardDeviceClaim.device_hash == device_hash))).first()
    if claimed or (previous and (previous.status != "rejected" or previous.user_id != user.id)):
        raise AppError("reward_already_submitted", "This account or browser has already submitted or earned this task. Contact support for shared school devices.", 409)
    if previous:
        previous.proof, previous.credits, previous.device_hash = proof, task.credits, device_hash
        previous.status, previous.submitted_at = "pending", utcnow()
        previous.reviewed_at, previous.reviewed_by, previous.review_note = None, None, None
        return previous
    row = RewardSubmission(task_id=task_id, user_id=user.id, email_hash=email_hash,
                           device_hash=device_hash, proof=proof, credits=task.credits)
    db.add(row)
    await db.flush()
    return row


async def approved_total(db, *, email_hash: str | None = None, since: datetime | None = None,
                         task_id: uuid.UUID | None = None, count: bool = False) -> int:
    expr = func.count() if count else func.coalesce(func.sum(RewardSubmission.credits), 0)
    query = select(expr).select_from(RewardSubmission).where(RewardSubmission.status == "approved")
    if email_hash:
        query = query.where(RewardSubmission.email_hash == email_hash)
    if since:
        query = query.where(RewardSubmission.reviewed_at >= since)
    if task_id:
        query = query.where(RewardSubmission.task_id == task_id)
    return int((await db.execute(query)).scalar_one())


async def review(db, actor: User, submission_id: uuid.UUID, approve: bool, note: str, request=None) -> RewardSubmission:
    # A single program lock protects cross-account budgets and browser claims;
    # the row lock + final status make retries incapable of awarding twice.
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('reward-approvals', 0))"))
    row = (await db.execute(select(RewardSubmission).where(RewardSubmission.id == submission_id).with_for_update())).scalars().first()
    if not row:
        raise AppError("not_found", "Task submission not found.", 404)
    if row.status != "pending":
        raise AppError("reward_reviewed", "This submission has already been reviewed.", 409)
    now = utcnow()
    if approve:
        user = await db.get(User, row.user_id) if row.user_id else None
        if user is None:
            raise AppError("reward_ineligible", "This account is unavailable.", 409)
        await billing.lock_plan_changes(db, user.id)
        if reason := await ineligible_reason(db, user):
            raise AppError("reward_ineligible", reason, 409)
        cfg = await program(db)
        task = await db.get(RewardTask, row.task_id)
        if not cfg.get("enabled") or not task or not task_open(task, now):
            raise AppError("reward_task_unavailable", "This task is paused, unpublished or expired; approval cannot award credits.", 409)
        if task.credits != row.credits:
            raise AppError("reward_changed", "The reward amount changed. Reject this submission with instructions to resubmit.", 409)
        start_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_month = start_day.replace(day=1)
        budgets = [("daily_credits", start_day, row.email_hash), ("monthly_credits", start_month, row.email_hash),
                   ("lifetime_credits", None, row.email_hash), ("global_daily_credits", start_day, None)]
        for key, since, email_hash in budgets:
            if await approved_total(db, email_hash=email_hash, since=since) + row.credits > int(cfg.get(key, 0)):
                raise AppError("reward_budget_reached", "This reward budget has been reached. Try approval later or adjust the program limits.", 409)
        if await approved_total(db, task_id=task.id, count=True) >= task.max_approvals:
            raise AppError("reward_task_budget_reached", "This task reached its approval limit.", 409)
        claimed = (await db.execute(select(RewardDeviceClaim.id).where(
            RewardDeviceClaim.task_id == task.id, RewardDeviceClaim.device_hash == row.device_hash))).first()
        if claimed:
            raise AppError("reward_device_used", "This browser already earned this task. Review shared-device eligibility through support.", 409)
        await usage.lock_user(db, user.id)
        row.expires_at = month_end(now)
        db.add(RewardDeviceClaim(task_id=task.id, device_hash=row.device_hash, submission_id=row.id))
        db.add(usage.ledger_entry(user.id, row.credits, "task_reward", ref=f"reward:{row.id}",
                                 actor_id=actor.id, event_type="CREDIT_REWARD", resource_type="reward_submission",
                                 resource_id=str(row.id), meta={"expires_at": row.expires_at.isoformat(), "task_id": str(task.id)}))
    row.status, row.reviewed_at, row.reviewed_by, row.review_note = "approved" if approve else "rejected", now, actor.id, note
    audit(db, actor.id, f"reward.{row.status}", request=request, target_user=row.user_id,
          target_type="reward_submission", target_id=str(row.id), reason=note,
          after={"status": row.status, "credits": row.credits if approve else 0})
    return row


def task_out(task: RewardTask) -> dict:
    out = {key: getattr(task, key) for key in ("title", "instructions", "credits", "published", "max_approvals")}
    return out | {"id": str(task.id), "starts_at": task.starts_at.isoformat() if task.starts_at else None,
                  "ends_at": task.ends_at.isoformat() if task.ends_at else None}


def submission_out(row: RewardSubmission, *, admin: bool = False) -> dict:
    out = {"id": str(row.id), "task_id": str(row.task_id), "credits": row.credits,
           "status": row.status, "submitted_at": row.submitted_at, "reviewed_at": row.reviewed_at,
           "review_note": row.review_note, "expires_at": row.expires_at}
    if admin:
        out.update({"user_id": str(row.user_id) if row.user_id else None, "proof": row.proof})
    return out
