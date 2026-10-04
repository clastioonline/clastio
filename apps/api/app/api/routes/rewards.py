"""Teacher task submissions and audited staff review; unpublished by default."""
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import select

from app.core.db import utcnow
from app.core.deps import DB, CurrentUser, require
from app.core.errors import AppError
from app.core.ratelimit import rate_limit
from app.models import AppSetting, RewardSubmission, RewardTask, TrialDeviceException, TrialGrant, User
from app.services import billing, rewards, settings
from app.services.events import audit
from app.services.trial_device import ensure_cookie

router = APIRouter(tags=["rewards"])
Viewer = Annotated[User, Depends(require("billing.view"))]
Manager = Annotated[User, Depends(require("billing.modify"))]


class ProofIn(BaseModel):
    proof: str = Field(min_length=20, max_length=2000)

    @model_validator(mode="after")
    def validate_proof(self):
        self.proof = self.proof.strip()
        if len(self.proof) < 20:
            raise ValueError("Explain how you completed the task in at least 20 characters.")
        return self


class TaskIn(BaseModel):
    title: str = Field(min_length=5, max_length=160)
    instructions: str = Field(min_length=20, max_length=4000)
    credits: int = Field(ge=1, le=20)
    published: bool = False
    max_approvals: int = Field(100, ge=1, le=5000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    # Staff attest to the task policy. No incentivised positive public reviews,
    # fabricated work, unsolicited messages or purchases are eligible tasks.
    policy_acknowledged: Literal[True]

    @model_validator(mode="after")
    def validate_window(self):
        for value in (self.starts_at, self.ends_at):
            if value and value.tzinfo is None:
                raise ValueError("Task dates must include a timezone.")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("The end must follow the start.")
        if self.published and self.ends_at and self.ends_at <= utcnow():
            raise ValueError("An expired task cannot be published.")
        self.title, self.instructions = self.title.strip(), self.instructions.strip()
        if len(self.title) < 5 or len(self.instructions) < 20:
            raise ValueError("Task title or instructions are too short.")
        return self


class ProgramIn(BaseModel):
    enabled: bool = False
    daily_credits: int = Field(20, ge=1, le=50)
    monthly_credits: int = Field(60, ge=1, le=200)
    lifetime_credits: int = Field(200, ge=1, le=500)
    global_daily_credits: int = Field(500, ge=1, le=2000)
    reason: str = Field(min_length=5, max_length=500)


class ReviewIn(BaseModel):
    approve: bool
    note: str = Field(min_length=5, max_length=500)


class ExceptionIn(BaseModel):
    email: EmailStr
    reason: str = Field(min_length=10, max_length=500)


@router.get("/rewards")
async def list_tasks(request: Request, response: Response, user: CurrentUser, db: DB):
    ensure_cookie(request, response)
    cfg = await settings.get_setting("rewards")
    reason = await rewards.ineligible_reason(db, user)
    now = utcnow()
    tasks = (await db.execute(select(RewardTask).where(RewardTask.published.is_(True)).order_by(RewardTask.created_at.desc()).limit(100))).scalars().all()
    submissions = (await db.execute(select(RewardSubmission).where(RewardSubmission.user_id == user.id)
                                   .order_by(RewardSubmission.submitted_at.desc()).limit(100))).scalars().all()
    from app.api.routes.auth import normalised_email_hash

    earned = await rewards.approved_total(db, email_hash=normalised_email_hash(user.email), since=now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
    return {"enabled": bool(cfg.get("enabled")), "eligible": reason is None, "ineligible_reason": reason,
            "limits": cfg, "earned_this_month": earned, "expires_at": rewards.month_end(now),
            "tasks": [rewards.task_out(task) for task in tasks if rewards.task_open(task, now)] if cfg.get("enabled") else [],
            "submissions": [rewards.submission_out(row) for row in submissions]}


@router.post("/rewards/tasks/{task_id}/submit", dependencies=[Depends(rate_limit("reward_submit", 10, 3600))])
async def submit_task(task_id: uuid.UUID, data: ProofIn, request: Request, response: Response, user: CurrentUser, db: DB):
    digest = ensure_cookie(request, response, strict=True)
    assert digest is not None
    row = await rewards.submit(db, user, task_id, data.proof, digest)
    await db.commit()
    return rewards.submission_out(row)


@router.get("/admin/rewards")
async def admin_tasks(actor: Viewer, db: DB):
    tasks = (await db.execute(select(RewardTask).order_by(RewardTask.created_at.desc()).limit(100))).scalars().all()
    pending = (await db.execute(select(RewardSubmission, User.email, RewardTask.title)
        .outerjoin(User, User.id == RewardSubmission.user_id).join(RewardTask, RewardTask.id == RewardSubmission.task_id)
        .where(RewardSubmission.status == "pending").order_by(RewardSubmission.submitted_at).limit(100))).all()
    return {"program": await settings.get_setting("rewards"), "tasks": [rewards.task_out(task) for task in tasks],
            "submissions": [rewards.submission_out(row, admin=True) | {"email": email, "task_title": title}
                            for row, email, title in pending]}


@router.put("/admin/rewards/program")
async def update_program(data: ProgramIn, request: Request, actor: Manager, db: DB):
    from sqlalchemy import text

    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('reward-approvals', 0))"))
    before = await settings.get_setting("rewards")
    after = data.model_dump(exclude={"reason"})
    row = await db.get(AppSetting, "rewards")
    if row:
        row.value, row.updated_at = after, utcnow()
    else:
        db.add(AppSetting(key="rewards", value=after))
    audit(db, actor.id, "reward.program_updated", request=request, before=before, after=after, reason=data.reason)
    await db.commit()
    settings._cache.pop("rewards", None)
    return {"ok": True}


@router.post("/admin/rewards/tasks")
async def add_task(data: TaskIn, request: Request, actor: Manager, db: DB):
    row = RewardTask(**data.model_dump(exclude={"policy_acknowledged"}), created_by=actor.id)
    db.add(row)
    await db.flush()
    audit(db, actor.id, "reward.task_created", request=request, target_type="reward_task", target_id=str(row.id), after=rewards.task_out(row))
    await db.commit()
    return rewards.task_out(row)


@router.put("/admin/rewards/tasks/{task_id}")
async def edit_task(task_id: uuid.UUID, data: TaskIn, request: Request, actor: Manager, db: DB):
    from sqlalchemy import text

    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('reward-approvals', 0))"))
    row = (await db.execute(select(RewardTask).where(RewardTask.id == task_id).with_for_update())).scalars().first()
    if not row:
        raise AppError("not_found", "Task not found.", 404)
    before = rewards.task_out(row)
    for key, value in data.model_dump(exclude={"policy_acknowledged"}).items():
        setattr(row, key, value)
    audit(db, actor.id, "reward.task_updated", request=request, target_type="reward_task", target_id=str(row.id), before=before, after=rewards.task_out(row))
    await db.commit()
    return rewards.task_out(row)


@router.post("/admin/rewards/submissions/{submission_id}/review")
async def review_submission(submission_id: uuid.UUID, data: ReviewIn, request: Request, actor: Manager, db: DB):
    row = await rewards.review(db, actor, submission_id, data.approve, data.note, request)
    await db.commit()
    return rewards.submission_out(row, admin=True)


@router.post("/admin/rewards/trial-exception")
async def allow_shared_trial(data: ExceptionIn, request: Request, actor: Annotated[User, Depends(require("users.manage", "billing.modify"))], db: DB):
    from app.api.routes.auth import normalised_email_hash

    user = (await db.execute(select(User).where(User.email == str(data.email).lower()))).scalars().first()
    if not user or user.role != "teacher" or not user.email_verified or user.status != "active":
        raise AppError("trial_exception_ineligible", "Choose an active teacher with a verified email.", 409)
    await billing.lock_plan_changes(db, user.id)
    previous = (await db.execute(select(TrialGrant.id).where(TrialGrant.email_hash == normalised_email_hash(user.email)))).first()
    if previous:
        raise AppError("trial_already_used", "This email already used a trial. A shared-device exception cannot grant another.", 409)
    row = await db.get(TrialDeviceException, user.id)
    if row:
        row.actor_id, row.reason = actor.id, data.reason
    else:
        db.add(TrialDeviceException(user_id=user.id, actor_id=actor.id, reason=data.reason))
    audit(db, actor.id, "trial.shared_device_exception", request=request, target_user=user.id, reason=data.reason)
    await db.commit()
    return {"ok": True, "message": "The teacher can explicitly start their own one-time trial on the shared browser. No trial was automatically started."}
