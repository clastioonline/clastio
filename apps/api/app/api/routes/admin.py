"""Admin console: user management, staff roles, security and audit views, global search, request trace and exports.

Every route checks an explicit permission on the server (see app/core/permissions.py). Every change is written to
the append-only audit log with before/after values and a reason. Admins never see or set passwords: support sends
the teacher a reset link instead.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import utcnow
from app.core.deps import DB, require, staff_permissions
from app.core.errors import AppError, Forbidden, NotFound
from app.core.pagination import clamp, keyset, page
from app.core.permissions import PERMISSIONS, ROLE_LABELS, ROLES
from app.models import (
    AIUsage,
    AnalyticsEvent,
    Announcement,
    ApiRequest,
    AuditLog,
    Consent,
    Course,
    CreditLedger,
    EmailOutbox,
    GenerationJob,
    LegalDocument,
    Payment,
    Plan,
    SecurityEvent,
    Subscription,
    SupportTicket,
    TicketMessage,
    User,
    UserNote,
    UserSession,
    WebhookEvent,
)
from app.services import billing, sessions, usage
from app.services.events import audit, security_event
from app.services.notify import notify, queue_email

router = APIRouter(prefix="/admin", tags=["admin"])


def Staff(*perms: str):  # noqa: N802 - reads like a type in signatures
    return Annotated[User, Depends(require(*perms))]


def _iso(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


def _uid(u: uuid.UUID | None) -> str | None:
    return str(u) if u else None


# --------------------------------------------------------------------------- staff roles


@router.get("/roles")
async def roles(_: Staff()):
    """The permission matrix, so the console can show what each staff role may do."""
    return {"permissions": PERMISSIONS,
            "roles": [{"code": r, "label": ROLE_LABELS[r], "permissions": sorted(p)} for r, p in ROLES.items()]}


@router.get("/staff")
async def staff(_: Staff("users.view"), db: DB):
    rows = (await db.execute(select(User).where(User.role == "admin").order_by(User.created_at))).scalars().all()
    return {"items": [{"id": str(u.id), "email": u.email, "name": u.name, "admin_role": u.admin_role or "admin",
                       "admin_role_label": ROLE_LABELS.get(u.admin_role or "admin"), "status": u.status,
                       "last_active_at": _iso(u.last_active_at)} for u in rows]}


# --------------------------------------------------------------------------- users: list


async def _plans_for(db: AsyncSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, Subscription]:
    if not user_ids:
        return {}
    rows = (await db.execute(select(Subscription).where(Subscription.user_id.in_(user_ids), _active_sub_clause())
                             .order_by(Subscription.created_at))).scalars().all()
    return {s.user_id: s for s in rows}  # latest wins


def _active_sub_clause():
    return and_(Subscription.status.in_(usage.ACTIVE_STATUSES),
                or_(Subscription.provider.notin_(usage.SELF_EXPIRING), Subscription.current_period_end.is_(None),
                    Subscription.current_period_end > func.now()))


def _user_row(u: User, sub: Subscription | None) -> dict[str, Any]:
    return {"id": str(u.id), "email": u.email, "name": u.name, "role": u.role,
            "admin_role": (u.admin_role or "admin") if u.role == "admin" else None, "status": u.status,
            "email_verified": u.email_verified, "plan": sub.plan_code if sub else "free",
            "plan_source": sub.provider if sub else None, "plan_status": sub.status if sub else None,
            "signup_source": u.signup_source, "created_at": u.created_at.isoformat(),
            "last_login_at": _iso(u.last_login_at), "last_active_at": _iso(u.last_active_at)}


SORTS = {"newest": (User.created_at.desc(), User.id.desc()), "oldest": (User.created_at.asc(), User.id.asc()),
         "last_active": (User.last_active_at.desc().nulls_last(), User.id.desc()),
         "email": (User.email.asc(), User.id.asc())}


@router.get("/users")
async def list_users(_: Staff("users.view"), db: DB, q: str | None = None, status: str | None = None,
                     plan: str | None = None, kind: str | None = None, verified: bool | None = None,
                     source: str | None = None, created_from: datetime | None = None,
                     created_to: datetime | None = None, sort: str = "newest", cursor: str | None = None,
                     limit: int = 50, offset: int = 0):
    """Search, filter and sort accounts. `cursor` paging works with the default newest-first sort; other sorts
    use offset."""
    query = select(User)
    if q:
        q = q.strip()
        try:
            query = query.where(User.id == uuid.UUID(q))
        except ValueError:
            like = f"%{q.replace('%', '').replace('_', ' ')}%"
            query = query.where(User.email.ilike(like) | User.name.ilike(like))
    if status == "email_unverified":
        query = query.where(User.email_verified.is_(False), User.status == "active")
    elif status:
        query = query.where(User.status == status)
    if kind == "staff":
        query = query.where(User.role == "admin")
    elif kind == "teacher":
        query = query.where(User.role != "admin")
    if verified is not None:
        query = query.where(User.email_verified.is_(verified))
    if source:
        query = query.where(User.signup_source == source)
    if created_from:
        query = query.where(User.created_at >= created_from)
    if created_to:
        query = query.where(User.created_at < created_to)
    if plan:
        has_plan = exists().where(Subscription.user_id == User.id, _active_sub_clause())
        if plan == "free":
            query = query.where(~has_plan)
        elif plan == "trial":
            query = query.where(exists().where(Subscription.user_id == User.id, _active_sub_clause(),
                                               Subscription.provider == "trial"))
        else:
            query = query.where(exists().where(Subscription.user_id == User.id, _active_sub_clause(),
                                               Subscription.plan_code == plan))
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    limit = clamp(limit)
    nxt = None
    if sort == "newest" and (cursor or not offset):
        rows = (await db.execute(keyset(query, User, cursor, limit))).scalars().all()
        rows, nxt = page(list(rows), limit)
    else:
        order = SORTS.get(sort, SORTS["newest"])
        rows = (await db.execute(query.order_by(*order).limit(limit).offset(max(0, offset)))).scalars().all()
    subs = await _plans_for(db, [u.id for u in rows])
    return {"items": [_user_row(u, subs.get(u.id)) for u in rows], "total": total, "next_cursor": nxt}


# --------------------------------------------------------------------------- users: detail


async def _target(db: AsyncSession, user_id: uuid.UUID) -> User:
    u = await db.get(User, user_id)
    if u is None:
        raise NotFound("User")
    return u


def _guard_staff_target(actor: User, target: User) -> None:
    """Only staff who can manage staff may act on another staff account, and nobody acts on themselves."""
    if actor.id == target.id:
        raise AppError("self_action", "You can't do this to your own account.", 409)
    if target.role == "admin" and "admins.manage" not in staff_permissions(actor):
        raise Forbidden("Only a super admin can change another staff account.")


@router.get("/users/{user_id}")
async def user_detail(user_id: uuid.UUID, admin: Staff("users.view"), request: Request, db: DB):
    u = await _target(db, user_id)
    perms = staff_permissions(admin)
    subs = (await db.execute(select(Subscription).where(Subscription.user_id == u.id)
                             .order_by(Subscription.created_at.desc()).limit(20))).scalars().all()
    active = await usage.active_subscription(db, u.id)
    sess_rows = (await db.execute(select(UserSession).where(UserSession.user_id == u.id)
                                  .order_by(UserSession.created_at.desc()).limit(20))).scalars().all()
    logins = (await db.execute(select(SecurityEvent).where(
        SecurityEvent.user_id == u.id, SecurityEvent.type.in_(("login_success", "login_failed", "new_device")))
        .order_by(SecurityEvent.created_at.desc()).limit(30))).scalars().all()
    sec = (await db.execute(select(SecurityEvent).where(SecurityEvent.user_id == u.id)
                            .order_by(SecurityEvent.created_at.desc()).limit(30))).scalars().all()
    audits = (await db.execute(select(AuditLog, User.email).outerjoin(User, User.id == AuditLog.actor_id)
                               .where(AuditLog.target == str(u.id)).order_by(AuditLog.created_at.desc()).limit(30))
              ).all()
    notes = (await db.execute(select(UserNote, User.email).outerjoin(User, User.id == UserNote.author_id)
                              .where(UserNote.user_id == u.id).order_by(UserNote.created_at.desc()).limit(50))).all()
    consents = (await db.execute(select(Consent).where(Consent.user_id == u.id)
                                 .order_by(Consent.created_at.desc()).limit(30))).scalars().all()
    ledger = (await db.execute(select(CreditLedger).where(CreditLedger.owner_id == u.id)
                               .order_by(CreditLedger.created_at.desc()).limit(40))).scalars().all()
    jobs = (await db.execute(select(GenerationJob).where(GenerationJob.owner_id == u.id)
                             .order_by(GenerationJob.created_at.desc()).limit(20))).scalars().all()
    projects = (await db.execute(select(Course).where(Course.owner_id == u.id).order_by(Course.created_at.desc())
                                 .limit(30))).scalars().all()
    out: dict[str, Any] = {
        "user": {**_user_row(u, active), "phone": u.phone, "locale": u.locale, "timezone": u.timezone,
                 "email_verified_at": _iso(u.email_verified_at), "suspended_reason": u.suspended_reason,
                 "deletion_requested_at": _iso(u.deletion_requested_at), "deleted_at": _iso(u.deleted_at),
                 "password_changed_at": _iso(u.password_changed_at), "signup_meta": u.signup_meta or {},
                 "has_password": bool(u.password_hash)},
        "usage": await usage.summary(db, u),
        "media_credits": await _media_balance(db, u),
        "subscriptions": [{"id": str(s.id), "plan": s.plan_code, "status": s.status, "provider": s.provider,
                           "interval": s.interval, "period_end": _iso(s.current_period_end),
                           "cancel_at_period_end": s.cancel_at_period_end, "created_at": s.created_at.isoformat()}
                          for s in subs],
        "sessions": [sessions.session_out(s) for s in sess_rows],
        "logins": [_sec_out(e) for e in logins],
        "security_events": [_sec_out(e) for e in sec],
        "audit": [_audit_out(a, email) for a, email in audits],
        "notes": [{"id": str(n.id), "body": n.body, "author": email, "created_at": n.created_at.isoformat()}
                  for n, email in notes],
        "consents": [{"kind": c.kind, "granted": c.granted, "version": c.version, "method": c.method,
                      "created_at": c.created_at.isoformat()} for c in consents],
        "ledger": [_ledger_out(r) for r in ledger],
        "jobs": [{"id": str(j.id), "type": j.type, "status": j.status, "error": j.error, "cost_usd": j.cost_usd,
                  "created_at": j.created_at.isoformat()} for j in jobs],
        "projects": [{"id": str(c.project_id), "topic": c.topic, "grade": c.grade, "status": c.status,
                      "created_at": c.created_at.isoformat()} for c in projects],
    }
    if "billing.view" in perms:
        pays = (await db.execute(select(Payment).where(Payment.user_id == u.id).order_by(Payment.created_at.desc())
                                 .limit(30))).scalars().all()
        out["payments"] = [_payment_out(p) for p in pays]
    # Data access log: viewing an account's personal data is itself recorded.
    audit(db, admin.id, "data_access.user_profile", request=request, target_user=u.id, target_type="user",
          target_id=str(u.id))
    await db.commit()
    return out


async def _media_balance(db: AsyncSession, u: User) -> int:
    total = (await db.execute(select(func.coalesce(func.sum(CreditLedger.amount), 0)).where(
        CreditLedger.owner_id == u.id, CreditLedger.resource == "media_credits"))).scalar_one()
    return int(total)


def _sec_out(e: SecurityEvent) -> dict[str, Any]:
    return {"id": str(e.id), "type": e.type, "severity": e.severity, "user_id": _uid(e.user_id), "ip": e.ip,
            "user_agent": e.user_agent, "request_id": e.request_id, "details": e.details,
            "created_at": e.created_at.isoformat()}


def _audit_out(a: AuditLog, actor_email: str | None) -> dict[str, Any]:
    return {"id": str(a.id), "action": a.action, "actor_id": _uid(a.actor_id), "actor": actor_email,
            "target": a.target, "target_type": a.target_type, "target_id": a.target_id, "before": a.before,
            "after": a.after, "reason": a.reason, "details": a.details, "ip": a.ip, "request_id": a.request_id,
            "created_at": a.created_at.isoformat()}


def _ledger_out(r: CreditLedger) -> dict[str, Any]:
    return {"id": str(r.id), "amount": r.amount, "resource": r.resource, "event_type": r.event_type,
            "reason": r.reason, "ref": r.ref, "actor_id": _uid(r.actor_id), "request_id": r.request_id,
            "note": (r.meta or {}).get("reason"), "created_at": r.created_at.isoformat()}


def _payment_out(p: Payment) -> dict[str, Any]:
    return {"id": str(p.id), "provider": p.provider, "provider_ref": p.provider_ref, "amount": float(p.amount),
            "currency": p.currency, "status": p.status, "invoice_id": p.invoice_id, "invoice_url": p.invoice_url,
            "failure_reason": p.failure_reason, "created_at": p.created_at.isoformat()}


@router.get("/users/{user_id}/timeline")
async def user_timeline(user_id: uuid.UUID, _: Staff("users.view"), db: DB, cursor: str | None = None,
                        limit: int = 50):
    """Product activity for one account (sign-ups, generations, purchases…), newest first."""
    limit = clamp(limit)
    rows = (await db.execute(keyset(select(AnalyticsEvent).where(AnalyticsEvent.user_id == user_id), AnalyticsEvent,
                                    cursor, limit))).scalars().all()
    rows, nxt = page(list(rows), limit)
    return {"items": [{"id": str(e.id), "name": e.name, "properties": e.properties,
                       "created_at": e.created_at.isoformat()} for e in rows], "next_cursor": nxt}


# --------------------------------------------------------------------------- users: actions


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class StatusIn(ReasonIn):
    status: str = Field(pattern="^(active|suspended|banned)$")
    notify_user: bool = True


@router.post("/users/{user_id}/status")
async def set_status(user_id: uuid.UUID, data: StatusIn, admin: Staff("users.manage"), request: Request, db: DB):
    """Suspend, ban or restore an account. Suspending or banning signs the account out everywhere at once."""
    u = await _target(db, user_id)
    _guard_staff_target(admin, u)
    if (data.status == "banned" or u.status == "banned") and "users.ban" not in staff_permissions(admin):
        raise Forbidden("Your role can't ban accounts or lift bans.")
    if u.status == "deleted":
        raise AppError("account_deleted", "This account has been deleted and can't be changed.", 409)
    if u.status == data.status:
        return {"ok": True, "status": u.status}
    before = {"status": u.status, "suspended_reason": u.suspended_reason}
    u.status = data.status
    u.suspended_reason = data.reason if data.status != "active" else None
    if data.status == "active":
        u.deletion_requested_at = None
    revoked = 0
    if data.status != "active":
        revoked = await sessions.revoke(db, u.id, reason=f"admin_{data.status}")
    ev = {"suspended": "account_suspended", "banned": "account_banned", "active": "account_restored"}[data.status]
    security_event(db, ev, user_id=u.id, request=request, by=str(admin.id))
    audit(db, admin.id, f"user.{ev.removeprefix('account_')}", request=request, target_user=u.id, target_type="user",
          target_id=str(u.id), before=before, after={"status": u.status}, reason=data.reason,
          sessions_revoked=revoked)
    if data.notify_user and u.role != "admin":
        from app.core.config import get_settings

        if data.status == "active":
            queue_email(db, u, "account_restored", link=f"{get_settings().public_web_url}/login")
        else:
            queue_email(db, u, "account_suspended", reason=data.reason)
    await db.commit()
    return {"ok": True, "status": u.status, "sessions_revoked": revoked}


@router.post("/users/{user_id}/force-logout")
async def force_logout(user_id: uuid.UUID, data: ReasonIn, admin: Staff("users.manage"), request: Request, db: DB):
    u = await _target(db, user_id)
    _guard_staff_target(admin, u)
    n = await sessions.revoke(db, u.id, reason="admin")
    security_event(db, "session_revoked", user_id=u.id, request=request, by=str(admin.id), count=n)
    audit(db, admin.id, "user.force_logout", request=request, target_user=u.id, target_type="user",
          target_id=str(u.id), reason=data.reason, sessions_revoked=n)
    await db.commit()
    return {"ok": True, "sessions_revoked": n}


@router.delete("/users/{user_id}/sessions/{session_id}")
async def revoke_one_session(user_id: uuid.UUID, session_id: uuid.UUID, admin: Staff("users.manage"),
                             request: Request, db: DB):
    u = await _target(db, user_id)
    _guard_staff_target(admin, u)
    n = await sessions.revoke(db, u.id, session_id=session_id, reason="admin")
    if not n:
        raise NotFound("Active session")
    audit(db, admin.id, "user.session_revoked", request=request, target_user=u.id, target_type="session",
          target_id=str(session_id))
    await db.commit()
    return {"ok": True}


class VerificationIn(BaseModel):
    action: str = Field(pattern="^(resend|mark_unverified|mark_verified)$")
    reason: str = Field("", max_length=500)


@router.post("/users/{user_id}/verification")
async def verification(user_id: uuid.UUID, data: VerificationIn, admin: Staff("users.manage"), request: Request,
                       db: DB):
    """Resend the verification email, or reset/force the verified flag (e.g. after an email change by support)."""
    from app.api.routes.auth import verification_link

    u = await _target(db, user_id)
    _guard_staff_target(admin, u)
    if data.action != "resend" and len(data.reason.strip()) < 3:
        raise AppError("reason_required", "Give a reason for changing verification.", 422)
    before = {"email_verified": u.email_verified}
    if data.action == "mark_unverified":
        u.email_verified, u.email_verified_at = False, None
    elif data.action == "mark_verified":
        u.email_verified, u.email_verified_at = True, utcnow()
    if data.action in ("resend", "mark_unverified"):
        queue_email(db, u, "verify_email", link=verification_link(u))
    audit(db, admin.id, f"user.verification_{data.action}", request=request, target_user=u.id, target_type="user",
          target_id=str(u.id), before=before, after={"email_verified": u.email_verified}, reason=data.reason or None)
    await db.commit()
    return {"ok": True, "email_verified": u.email_verified}


@router.post("/users/{user_id}/password-reset")
async def send_password_reset(user_id: uuid.UUID, admin: Staff("users.manage"), request: Request, db: DB):
    """Email the teacher a reset link. Staff never see or choose passwords."""
    from app.api.routes.auth import reset_link

    u = await _target(db, user_id)
    _guard_staff_target(admin, u)
    if u.status != "active":
        raise AppError("account_inactive", "Restore the account before sending a reset link.", 409)
    queue_email(db, u, "password_reset", link=reset_link(u))
    audit(db, admin.id, "user.password_reset_sent", request=request, target_user=u.id, target_type="user",
          target_id=str(u.id))
    await db.commit()
    return {"ok": True}


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


@router.post("/users/{user_id}/notes")
async def add_note(user_id: uuid.UUID, data: NoteIn, admin: Staff("users.manage"), request: Request, db: DB):
    u = await _target(db, user_id)
    n = UserNote(user_id=u.id, author_id=admin.id, body=data.body.strip())
    db.add(n)
    await db.flush()
    audit(db, admin.id, "user.note_added", request=request, target_user=u.id, target_type="note", target_id=str(n.id))
    await db.commit()
    return {"id": str(n.id), "body": n.body, "author": admin.email, "created_at": n.created_at.isoformat()}


class CreditsIn(ReasonIn):
    resource: str = Field("credits", pattern="^(credits|media_credits)$")
    amount: int = Field(ge=-100_000, le=100_000)


@router.post("/users/{user_id}/credits")
async def adjust_credits(user_id: uuid.UUID, data: CreditsIn, admin: Staff("billing.modify"), request: Request,
                         db: DB):
    """Grant (positive) or remove (negative) credits. Written to the ledger with the staff member and reason."""
    if data.amount == 0:
        raise AppError("invalid_amount", "Amount can't be zero.", 422)
    u = await _target(db, user_id)
    row = await usage.adjust(db, u.id, data.amount, resource=data.resource, reason=data.reason, actor_id=admin.id)
    await db.flush()
    audit(db, admin.id, "credits.adjusted", request=request, target_user=u.id, target_type="credit_ledger",
          target_id=str(row.id), after={"resource": data.resource, "amount": data.amount}, reason=data.reason)
    if data.amount > 0:
        await notify(db, u.id, "billing", f"{data.amount} {data.resource.replace('_', ' ')} added",
                     "Our team added credits to your account.", "/billing")
    await db.commit()
    return {"ok": True, "ledger": _ledger_out(row)}


class PlanIn(ReasonIn):
    plan: str | None = None
    months: int = Field(1, ge=1, le=36)
    extend_trial_days: int | None = Field(None, ge=1, le=90)
    end_manual: bool = False


@router.post("/users/{user_id}/plan")
async def change_plan(user_id: uuid.UUID, data: PlanIn, admin: Staff("billing.modify"), request: Request, db: DB):
    """Grant a plan for N months, extend a trial, or end a staff-granted plan. Gateway subscriptions are changed
    in the payment gateway so the teacher is never charged for a plan they no longer have."""
    u = await _target(db, user_id)
    if u.role == "admin":
        raise AppError("staff_account", "Staff accounts don't have plans.", 409)
    current = await usage.active_subscription(db, u.id)
    before = {"plan": current.plan_code if current else "free", "provider": current.provider if current else None,
              "period_end": _iso(current.current_period_end) if current else None}
    if current and current.provider in ("stripe", "dodo") and (data.plan or data.extend_trial_days or data.end_manual):
        raise AppError("paid_subscription", "This teacher pays through the payment gateway. Change or cancel their "
                       "plan there first.", 409)
    if data.plan:
        if await db.get(Plan, data.plan) is None:
            raise AppError("bad_request", "Unknown plan", 400)
        await billing.set_manual_plan(db, u.id, data.plan, months=data.months)
    elif data.extend_trial_days:
        trial = current if current and current.provider == "trial" else None
        if trial is None:
            trial = await usage.start_trial(db, u)
            if trial is None:
                raise AppError("trial_disabled", "Trials are switched off in Plans & trial.", 409)
            trial.current_period_end = utcnow()
        trial.current_period_end = max(trial.current_period_end, utcnow()) + timedelta(days=data.extend_trial_days)
    elif data.end_manual:
        if not current or current.provider not in ("manual", "trial"):
            raise AppError("nothing_to_end", "There's no staff-granted plan or trial to end.", 409)
        current.status, current.canceled_at = "canceled", utcnow()
    else:
        raise AppError("bad_request", "Choose a plan, a trial extension or end the current grant.", 400)
    await db.flush()
    after_sub = await usage.active_subscription(db, u.id)
    after = {"plan": after_sub.plan_code if after_sub else "free",
             "provider": after_sub.provider if after_sub else None,
             "period_end": _iso(after_sub.current_period_end) if after_sub else None}
    audit(db, admin.id, "user.plan_changed", request=request, target_user=u.id, target_type="subscription",
          target_id=str(after_sub.id) if after_sub else None, before=before, after=after, reason=data.reason)
    await db.commit()
    return {"ok": True, **after}


class StaffRoleIn(ReasonIn):
    admin_role: str | None = Field(None, pattern="^(super_admin|admin|support|analyst|finance|moderator)$")


@router.put("/users/{user_id}/staff-role")
async def set_staff_role(user_id: uuid.UUID, data: StaffRoleIn, admin: Staff("admins.manage"), request: Request,
                         db: DB):
    """Make an account staff with a role, change the role, or (admin_role = null) remove staff access."""
    from app.core.config import get_settings
    if get_settings().clerk_secret_key:
        raise AppError("clerk_roles_managed", "Manage staff roles in Clerk public metadata.", 409)
    u = await _target(db, user_id)
    if u.id == admin.id:
        raise AppError("self_action", "Ask another super admin to change your own role.", 409)
    before = {"role": u.role, "admin_role": u.admin_role}
    if u.role == "admin" and (u.admin_role or "admin") == "super_admin" and data.admin_role != "super_admin":
        others = (await db.execute(select(func.count()).select_from(User).where(
            User.role == "admin", User.admin_role == "super_admin", User.status == "active", User.id != u.id))
        ).scalar_one()
        if others == 0:
            raise AppError("last_super_admin", "There must always be at least one active super admin.", 409)
    if data.admin_role:
        u.role, u.admin_role = "admin", data.admin_role
    else:
        u.role, u.admin_role = "teacher", None
    await sessions.revoke(db, u.id, reason="role_change")  # new permissions apply from the next sign-in
    security_event(db, "admin_role_changed", user_id=u.id, request=request, by=str(admin.id),
                   before=before["admin_role"], after=u.admin_role)
    audit(db, admin.id, "staff.role_changed", request=request, target_user=u.id, target_type="user",
          target_id=str(u.id), before=before, after={"role": u.role, "admin_role": u.admin_role}, reason=data.reason)
    await db.commit()
    return {"ok": True, "role": u.role, "admin_role": u.admin_role}


# --------------------------------------------------------------------------- security events & audit log


@router.get("/security-events")
async def security_events(_: Staff("security.view"), db: DB, type: str | None = None, severity: str | None = None,
                          user_id: uuid.UUID | None = None, ip: str | None = None, days: int = 30,
                          cursor: str | None = None, limit: int = 50):
    q = select(SecurityEvent).where(SecurityEvent.created_at >= utcnow() - timedelta(days=min(days, 400)))
    if type:
        q = q.where(SecurityEvent.type == type)
    if severity:
        q = q.where(SecurityEvent.severity == severity)
    if user_id:
        q = q.where(SecurityEvent.user_id == user_id)
    if ip:
        q = q.where(SecurityEvent.ip == ip)
    limit = clamp(limit)
    rows, nxt = page(list((await db.execute(keyset(q, SecurityEvent, cursor, limit))).scalars().all()), limit)
    since = utcnow() - timedelta(days=1)
    summary = (await db.execute(select(SecurityEvent.type, SecurityEvent.severity, func.count())
                                .where(SecurityEvent.created_at >= since)
                                .group_by(SecurityEvent.type, SecurityEvent.severity))).all()
    emails = await _emails(db, [e.user_id for e in rows])
    return {"items": [{**_sec_out(e), "email": emails.get(e.user_id)} for e in rows], "next_cursor": nxt,
            "last_24h": [{"type": t, "severity": s, "count": c} for t, s, c in summary]}


async def _emails(db: AsyncSession, ids: list[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    ids = [i for i in set(ids) if i]
    if not ids:
        return {}
    return dict((await db.execute(select(User.id, User.email).where(User.id.in_(ids)))).all())


@router.get("/audit-logs")
async def audit_logs(_: Staff("audit.view"), db: DB, action: str | None = None, actor_id: uuid.UUID | None = None,
                     target: str | None = None, days: int = 90, cursor: str | None = None, limit: int = 50):
    q = select(AuditLog).where(AuditLog.created_at >= utcnow() - timedelta(days=min(days, 3650)))
    if action:
        q = q.where(AuditLog.action.like(f"{action.replace('%', '')}%"))
    if actor_id:
        q = q.where(AuditLog.actor_id == actor_id)
    if target:
        q = q.where(or_(AuditLog.target == target, AuditLog.target_id == target))
    limit = clamp(limit)
    rows, nxt = page(list((await db.execute(keyset(q, AuditLog, cursor, limit))).scalars().all()), limit)
    emails = await _emails(db, [a.actor_id for a in rows] + [_as_uuid(a.target) for a in rows])
    return {"items": [{**_audit_out(a, emails.get(a.actor_id)), "target_email": emails.get(_as_uuid(a.target))}
                      for a in rows], "next_cursor": nxt}


def _as_uuid(v: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(v) if v else None
    except ValueError:
        return None


# --------------------------------------------------------------------------- global search & request trace


@router.get("/search")
async def search(_: Staff("users.view"), db: DB, q: str):
    """One box for everything: an email, a name, a user/job/payment id, a request id (req_…) or a ticket number."""
    q = q.strip()
    if len(q) < 2:
        return {"users": [], "jobs": [], "payments": [], "tickets": [], "request": None}
    out: dict[str, Any] = {"users": [], "jobs": [], "payments": [], "tickets": [], "request": None}
    as_id = _as_uuid(q)
    uq = select(User)
    uq = uq.where(User.id == as_id) if as_id else uq.where(User.email.ilike(f"%{q}%") | User.name.ilike(f"%{q}%"))
    out["users"] = [{"id": str(u.id), "email": u.email, "name": u.name, "status": u.status}
                    for u in (await db.execute(uq.limit(10))).scalars().all()]
    if as_id:
        j = await db.get(GenerationJob, as_id)
        if j:
            out["jobs"].append({"id": str(j.id), "type": j.type, "status": j.status, "owner_id": _uid(j.owner_id)})
        p = await db.get(Payment, as_id)
        if p:
            out["payments"].append(_payment_out(p))
    pays = (await db.execute(select(Payment).where(or_(Payment.provider_ref == q, Payment.invoice_id == q))
                             .limit(5))).scalars().all()
    out["payments"] += [_payment_out(p) for p in pays]
    number = q.lstrip("#")
    if number.isdigit():
        t = (await db.execute(select(SupportTicket).where(SupportTicket.number == int(number)))).scalars().first()
        if t:
            out["tickets"].append({"id": str(t.id), "number": t.number, "subject": t.subject, "status": t.status})
    if q.startswith("req_") or len(q) in (16, 20):
        hit = (await db.execute(select(ApiRequest.request_id).where(ApiRequest.request_id == q))).first()
        if hit:
            out["request"] = q
    return out


@router.get("/trace/{request_id}")
async def trace(request_id: str, _: Staff("system.logs.view"), db: DB):
    """Everything recorded under one request id: the request, AI calls, jobs, credits, security and audit events."""
    req = (await db.execute(select(ApiRequest).where(ApiRequest.request_id == request_id))).scalars().first()
    ai = (await db.execute(select(AIUsage).where(AIUsage.request_id == request_id).order_by(AIUsage.created_at))
          ).scalars().all()
    jobs = (await db.execute(select(GenerationJob).where(GenerationJob.request_id == request_id))).scalars().all()
    ledger = (await db.execute(select(CreditLedger).where(CreditLedger.request_id == request_id))).scalars().all()
    sec = (await db.execute(select(SecurityEvent).where(SecurityEvent.request_id == request_id))).scalars().all()
    aud = (await db.execute(select(AuditLog).where(AuditLog.request_id == request_id))).scalars().all()
    job_ids = [j.id for j in jobs]
    if job_ids:  # AI calls made by the worker for those jobs
        ai += (await db.execute(select(AIUsage).where(AIUsage.job_id.in_(job_ids), AIUsage.request_id.is_(None)))
               ).scalars().all()
    if not any((req, ai, jobs, ledger, sec, aud)):
        raise NotFound("Request")
    return {
        "request": {"request_id": req.request_id, "method": req.method, "route": req.route, "status": req.status,
                    "duration_ms": req.duration_ms, "error_code": req.error_code, "user_id": _uid(req.user_id),
                    "ip": req.ip, "created_at": req.created_at.isoformat()} if req else None,
        "ai_calls": [{"id": str(a.id), "task": a.task, "provider": a.provider, "model": a.model,
                      "input_tokens": a.input_tokens, "output_tokens": a.output_tokens, "cost_usd": a.cost_usd,
                      "latency_ms": a.latency_ms, "success": a.success, "error_code": a.error_code,
                      "job_id": _uid(a.job_id), "created_at": a.created_at.isoformat()} for a in ai],
        "jobs": [{"id": str(j.id), "type": j.type, "status": j.status, "attempts": j.attempts, "error": j.error,
                  "created_at": j.created_at.isoformat()} for j in jobs],
        "ledger": [_ledger_out(r) for r in ledger],
        "security_events": [_sec_out(e) for e in sec],
        "audit": [_audit_out(a, None) for a in aud],
    }


# --------------------------------------------------------------------------- payments


@router.get("/payments")
async def payments(_: Staff("billing.view"), db: DB, status: str | None = None, provider: str | None = None,
                   cursor: str | None = None, limit: int = 50):
    q = select(Payment)
    if status:
        q = q.where(Payment.status == status)
    if provider:
        q = q.where(Payment.provider == provider)
    limit = clamp(limit)
    rows, nxt = page(list((await db.execute(keyset(q, Payment, cursor, limit))).scalars().all()), limit)
    emails = await _emails(db, [p.user_id for p in rows])
    since = utcnow() - timedelta(days=30)
    summary = (await db.execute(select(Payment.status, func.count(), func.coalesce(func.sum(Payment.amount), 0))
                                .where(Payment.created_at >= since).group_by(Payment.status))).all()
    return {"items": [{**_payment_out(p), "user_id": str(p.user_id), "email": emails.get(p.user_id)} for p in rows],
            "next_cursor": nxt,
            "last_30d": [{"status": s, "count": n, "amount": round(float(a), 2)} for s, n, a in summary]}


# --------------------------------------------------------------------------- webhooks & emails


@router.get("/webhooks")
async def webhooks(_: Staff("system.logs.view"), db: DB, provider: str | None = None, status: str | None = None,
                   cursor: str | None = None, limit: int = 50):
    q = select(WebhookEvent)
    if provider:
        q = q.where(WebhookEvent.provider == provider)
    if status:
        q = q.where(WebhookEvent.status == status)
    limit = clamp(limit)
    rows, nxt = page(list((await db.execute(keyset(q, WebhookEvent, cursor, limit))).scalars().all()), limit)
    return {"items": [{"id": str(w.id), "provider": w.provider, "event_id": w.event_id, "type": w.type,
                       "status": w.status, "result": w.result, "retry_count": w.retry_count,
                       "error_message": w.error_message, "payload_hash": w.payload_hash,
                       "processed_at": _iso(w.processed_at), "created_at": w.created_at.isoformat()} for w in rows],
            "next_cursor": nxt}


@router.get("/emails")
async def emails(_: Staff("system.logs.view"), db: DB, status: str | None = None, template: str | None = None,
                 cursor: str | None = None, limit: int = 50):
    q = select(EmailOutbox)
    if status:
        q = q.where(EmailOutbox.status == status)
    if template:
        q = q.where(EmailOutbox.template == template)
    limit = clamp(limit)
    rows, nxt = page(list((await db.execute(keyset(q, EmailOutbox, cursor, limit))).scalars().all()), limit)
    return {"items": [{"id": str(e.id), "to": e.to_email, "template": e.template, "subject": e.subject,
                       "status": e.status, "attempts": e.attempts, "last_error": e.last_error,
                       "sent_at": _iso(e.sent_at), "created_at": e.created_at.isoformat()} for e in rows],
            "next_cursor": nxt}


@router.post("/emails/{email_id}/retry")
async def retry_email(email_id: uuid.UUID, admin: Staff("support.manage"), request: Request, db: DB):
    e = await db.get(EmailOutbox, email_id)
    if e is None:
        raise NotFound("Email")
    if e.status != "failed":
        raise AppError("not_failed", "Only failed emails can be retried.", 409)
    e.status, e.attempts, e.send_after = "queued", 0, utcnow()
    audit(db, admin.id, "email.retry", request=request, target_user=e.user_id, target_type="email",
          target_id=str(e.id))
    await db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- exports


EXPORTS: dict[str, tuple[str, ...]] = {
    "users": ("users.view",),
    "payments": ("billing.view",),
    "subscriptions": ("billing.view",),
    "ai_usage": ("api_usage.view",),
    "credit_ledger": ("billing.view",),
    "security_events": ("security.view",),
    "audit_logs": ("audit.view",),
}
EXPORT_MAX_ROWS = 50_000


async def _export_rows(db: AsyncSession, dataset: str, since: datetime) -> list[dict[str, Any]]:
    if dataset == "users":
        rows = (await db.execute(select(User).where(User.created_at >= since).order_by(User.created_at)
                                 .limit(EXPORT_MAX_ROWS))).scalars().all()
        subs = await _plans_for(db, [u.id for u in rows])
        # No password hashes, tokens or free-text profile content.
        return [{k: v for k, v in _user_row(u, subs.get(u.id)).items()} for u in rows]
    if dataset == "payments":
        rows = (await db.execute(select(Payment, User.email).join(User, User.id == Payment.user_id)
                                 .where(Payment.created_at >= since).order_by(Payment.created_at)
                                 .limit(EXPORT_MAX_ROWS))).all()
        return [{**_payment_out(p), "email": e} for p, e in rows]
    if dataset == "subscriptions":
        rows = (await db.execute(select(Subscription, User.email).join(User, User.id == Subscription.user_id)
                                 .where(Subscription.created_at >= since).order_by(Subscription.created_at)
                                 .limit(EXPORT_MAX_ROWS))).all()
        return [{"id": str(s.id), "email": e, "plan": s.plan_code, "status": s.status, "provider": s.provider,
                 "interval": s.interval, "period_start": _iso(s.current_period_start),
                 "period_end": _iso(s.current_period_end), "cancel_at_period_end": s.cancel_at_period_end,
                 "created_at": s.created_at.isoformat()} for s, e in rows]
    if dataset == "ai_usage":
        rows = (await db.execute(select(AIUsage).where(AIUsage.created_at >= since).order_by(AIUsage.created_at)
                                 .limit(EXPORT_MAX_ROWS))).scalars().all()
        return [{"id": str(a.id), "user_id": _uid(a.owner_id), "job_id": _uid(a.job_id), "task": a.task,
                 "provider": a.provider, "model": a.model, "input_tokens": a.input_tokens,
                 "output_tokens": a.output_tokens, "cached_tokens": a.cached_tokens, "images": a.images,
                 "cost_usd": a.cost_usd, "latency_ms": a.latency_ms, "success": a.success,
                 "error_code": a.error_code, "request_id": a.request_id, "created_at": a.created_at.isoformat()}
                for a in rows]
    if dataset == "credit_ledger":
        rows = (await db.execute(select(CreditLedger).where(CreditLedger.created_at >= since)
                                 .order_by(CreditLedger.created_at).limit(EXPORT_MAX_ROWS))).scalars().all()
        return [{**_ledger_out(r), "user_id": str(r.owner_id)} for r in rows]
    if dataset == "security_events":
        rows = (await db.execute(select(SecurityEvent).where(SecurityEvent.created_at >= since)
                                 .order_by(SecurityEvent.created_at).limit(EXPORT_MAX_ROWS))).scalars().all()
        return [_sec_out(e) for e in rows]
    rows = (await db.execute(select(AuditLog).where(AuditLog.created_at >= since).order_by(AuditLog.created_at)
                             .limit(EXPORT_MAX_ROWS))).scalars().all()
    return [_audit_out(a, None) for a in rows]


@router.get("/export/{dataset}")
async def export(dataset: str, admin: Staff("data.export"), request: Request, db: DB, format: str = "csv",
                 days: int = 30):
    """Download a dataset as CSV or JSON. Each export is recorded in the audit log."""
    if dataset not in EXPORTS:
        raise NotFound("Dataset")
    missing = [p for p in EXPORTS[dataset] if p not in staff_permissions(admin)]
    if missing:
        raise Forbidden(f"Your role doesn't allow exporting {dataset}.")
    if format not in ("csv", "json"):
        raise AppError("bad_request", "Format must be csv or json.", 400)
    since = utcnow() - timedelta(days=max(1, min(days, 3650)))
    rows = await _export_rows(db, dataset, since)
    audit(db, admin.id, "data.export", request=request, target_type="dataset", target_id=dataset,
          after={"rows": len(rows), "format": format, "days": days})
    await db.commit()
    name = f"clastioenie-{dataset}-{utcnow():%Y%m%d}.{format}"
    headers = {"content-disposition": f'attachment; filename="{name}"', "cache-control": "no-store"}
    if format == "json":
        return Response(json.dumps(rows, default=str), media_type="application/json", headers=headers)
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: _csv_safe(v) for k, v in r.items()})
    return Response(buf.getvalue(), media_type="text/csv", headers=headers)


def _csv_safe(v: Any) -> Any:
    """Serialise nested values and neutralise spreadsheet formula injection."""
    if isinstance(v, dict | list):
        v = json.dumps(v, default=str)
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


# --------------------------------------------------------------------------- support tickets


@router.get("/support/tickets")
async def support_tickets(_: Staff("support.manage"), db: DB, status: str | None = None, kind: str | None = None,
                          priority: str | None = None, assigned: str | None = None, cursor: str | None = None,
                          limit: int = 50):
    from app.api.routes.account import ticket_out

    q = select(SupportTicket)
    if status == "active":
        q = q.where(SupportTicket.status.in_(("open", "pending")))
    elif status:
        q = q.where(SupportTicket.status == status)
    if kind:
        q = q.where(SupportTicket.kind == kind)
    if priority:
        q = q.where(SupportTicket.priority == priority)
    if assigned == "none":
        q = q.where(SupportTicket.assigned_to.is_(None))
    elif assigned:
        q = q.where(SupportTicket.assigned_to == _as_uuid(assigned))
    limit = clamp(limit)
    rows, nxt = page(list((await db.execute(keyset(q, SupportTicket, cursor, limit))).scalars().all()), limit)
    emails = await _emails(db, [t.user_id for t in rows] + [t.assigned_to for t in rows])
    counts = dict((await db.execute(select(SupportTicket.status, func.count()).group_by(SupportTicket.status))).all())
    return {"items": [{**ticket_out(t, email=emails.get(t.user_id)), "assigned_to": emails.get(t.assigned_to)}
                      for t in rows], "next_cursor": nxt, "counts": counts}


@router.get("/support/tickets/{ticket_id}")
async def support_ticket(ticket_id: uuid.UUID, _: Staff("support.manage"), db: DB):
    from app.api.routes.account import message_out, ticket_out

    t = await db.get(SupportTicket, ticket_id)
    if t is None:
        raise NotFound("Ticket")
    rows = (await db.execute(select(TicketMessage, User).outerjoin(User, User.id == TicketMessage.author_id)
                             .where(TicketMessage.ticket_id == t.id).order_by(TicketMessage.created_at))).all()
    owner = await db.get(User, t.user_id)
    return {**ticket_out(t, email=owner.email if owner else None), "user_id": str(t.user_id),
            "assigned_to": _uid(t.assigned_to), "request_id": t.request_id,
            "messages": [message_out(m, a, staff_view=True) for m, a in rows]}


class StaffReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)
    internal: bool = False
    status: str | None = Field(None, pattern="^(open|pending|resolved|closed|planned|declined)$")


@router.post("/support/tickets/{ticket_id}/messages")
async def support_reply(ticket_id: uuid.UUID, data: StaffReplyIn, admin: Staff("support.manage"), request: Request,
                        db: DB):
    from app.core.config import get_settings

    t = await db.get(SupportTicket, ticket_id)
    if t is None:
        raise NotFound("Ticket")
    db.add(TicketMessage(ticket_id=t.id, author_id=admin.id, body=data.body.strip(), internal=data.internal))
    if not data.internal:
        t.status = data.status or "pending"  # waiting on the teacher
        owner = await db.get(User, t.user_id)
        link = f"{get_settings().public_web_url}/support/{t.id}"
        await notify(db, t.user_id, "account", f"Reply on request #{t.number}", t.subject, f"/support/{t.id}")
        if owner and owner.status == "active":
            queue_email(db, owner, "ticket_reply", link=link, number=str(t.number), subject=t.subject,
                        reply=data.body.strip()[:2000])
    elif data.status:
        t.status = data.status
    if t.status in ("resolved", "closed") and not t.resolved_at:
        t.resolved_at = utcnow()
    t.updated_at = utcnow()
    audit(db, admin.id, "support.replied", request=request, target_user=t.user_id, target_type="ticket",
          target_id=str(t.id), internal=data.internal, status=t.status)
    await db.commit()
    return {"ok": True, "status": t.status}


class TicketPatch(BaseModel):
    status: str | None = Field(None, pattern="^(open|pending|resolved|closed|planned|declined)$")
    priority: str | None = Field(None, pattern="^(low|normal|high|urgent)$")
    assigned_to: uuid.UUID | None = None
    unassign: bool = False
    category: str | None = Field(None, max_length=60)


@router.patch("/support/tickets/{ticket_id}")
async def support_update(ticket_id: uuid.UUID, data: TicketPatch, admin: Staff("support.manage"), request: Request,
                         db: DB):
    t = await db.get(SupportTicket, ticket_id)
    if t is None:
        raise NotFound("Ticket")
    before = {"status": t.status, "priority": t.priority, "assigned_to": _uid(t.assigned_to), "category": t.category}
    if data.assigned_to:
        staff_user = await db.get(User, data.assigned_to)
        if staff_user is None or staff_user.role != "admin":
            raise AppError("bad_request", "Tickets can only be assigned to staff.", 400)
        t.assigned_to = staff_user.id
    if data.unassign:
        t.assigned_to = None
    for f in ("status", "priority", "category"):
        if getattr(data, f) is not None:
            setattr(t, f, getattr(data, f))
    if t.status in ("resolved", "closed") and not t.resolved_at:
        t.resolved_at = utcnow()
    t.updated_at = utcnow()
    audit(db, admin.id, "support.updated", request=request, target_user=t.user_id, target_type="ticket",
          target_id=str(t.id), before=before,
          after={"status": t.status, "priority": t.priority, "assigned_to": _uid(t.assigned_to),
                 "category": t.category})
    await db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- announcements


class AnnouncementIn(BaseModel):
    kind: str = Field("product", pattern="^(maintenance|product|feature|important)$")
    title: str = Field(min_length=3, max_length=200)
    body: str = Field("", max_length=2000)
    link: str | None = Field(None, max_length=300, pattern=r"^(/|https://)")
    audience: str = Field("teachers", pattern="^(teachers|everyone|staff)$")
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    active: bool = True
    notify_users: bool = False  # also drop it into everyone's notification list


@router.get("/announcements")
async def announcements(_: Staff("announcements.manage"), db: DB):
    from app.api.routes.account import announcement_out

    rows = (await db.execute(select(Announcement).order_by(Announcement.created_at.desc()).limit(100))).scalars().all()
    return {"items": [announcement_out(a) for a in rows]}


@router.post("/announcements")
async def create_announcement(data: AnnouncementIn, admin: Staff("announcements.manage"), request: Request, db: DB):
    from app.api.routes.account import announcement_out

    a = Announcement(**{**data.model_dump(exclude_none=True, exclude={"notify_users"}),
                        "starts_at": data.starts_at or utcnow()}, created_by=admin.id)
    db.add(a)
    await db.flush()
    if data.notify_users and a.active:
        from app.services.notifications import broadcast

        await broadcast(db, title=a.title, body=a.body, link=a.link, audience=a.audience,
                        dedupe_key=f"announcement:{a.id}")
    audit(db, admin.id, "announcement.created", request=request, target_type="announcement", target_id=str(a.id),
          after=announcement_out(a))
    await db.commit()
    return announcement_out(a)


@router.put("/announcements/{announcement_id}")
async def update_announcement(announcement_id: uuid.UUID, data: AnnouncementIn,
                              admin: Staff("announcements.manage"), request: Request, db: DB):
    from app.api.routes.account import announcement_out

    a = await db.get(Announcement, announcement_id)
    if a is None:
        raise NotFound("Announcement")
    before = announcement_out(a)
    for k, v in data.model_dump(exclude={"notify_users"}).items():
        if k == "starts_at" and v is None:
            continue
        setattr(a, k, v)
    audit(db, admin.id, "announcement.updated", request=request, target_type="announcement", target_id=str(a.id),
          before=before, after=announcement_out(a))
    await db.commit()
    return announcement_out(a)


# --------------------------------------------------------------------------- legal documents


class LegalIn(BaseModel):
    document_type: str
    version: str = Field(min_length=1, max_length=20, pattern=r"^[0-9A-Za-z.\-]+$")
    title: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=20, max_length=200_000)
    summary_of_changes: str | None = Field(None, max_length=5000)
    requires_acceptance: bool = False
    effective_from: datetime | None = None


@router.get("/legal")
async def legal_documents(_: Staff("legal.manage"), db: DB):
    from app.services import legal as legal_svc

    rows = (await db.execute(select(LegalDocument).order_by(LegalDocument.document_type,
                                                             LegalDocument.created_at.desc()))).scalars().all()
    accepted = dict((await db.execute(select(Consent.document_id, func.count(func.distinct(Consent.user_id)))
                                      .where(Consent.granted.is_(True), Consent.document_id.is_not(None))
                                      .group_by(Consent.document_id))).all())
    return {"types": legal_svc.DOC_TYPES,
            "items": [{**legal_svc.doc_out(d), "accepted_by": accepted.get(d.id, 0)} for d in rows]}


@router.get("/legal/{doc_id}")
async def legal_document_detail(doc_id: uuid.UUID, _: Staff("legal.manage"), db: DB):
    from app.services import legal as legal_svc

    d = await db.get(LegalDocument, doc_id)
    if d is None:
        raise NotFound("Document")
    return legal_svc.doc_out(d, content=True)


@router.post("/legal")
async def create_legal_draft(data: LegalIn, admin: Staff("legal.manage"), request: Request, db: DB):
    from app.services import legal as legal_svc

    if data.document_type not in legal_svc.DOC_TYPES:
        raise AppError("bad_request", "Unknown document type.", 400)
    dup = (await db.execute(select(LegalDocument.id).where(LegalDocument.document_type == data.document_type,
                                                           LegalDocument.version == data.version))).first()
    if dup:
        raise AppError("version_exists", "That version already exists. Published versions can't be changed; "
                       "use a new version number.", 409)
    d = LegalDocument(**data.model_dump(), status="draft", created_by=admin.id)
    db.add(d)
    await db.flush()
    audit(db, admin.id, "legal.draft_created", request=request, target_type="legal_document", target_id=str(d.id),
          after={"type": d.document_type, "version": d.version})
    await db.commit()
    return legal_svc.doc_out(d, content=True)


@router.put("/legal/{doc_id}")
async def update_legal_draft(doc_id: uuid.UUID, data: LegalIn, admin: Staff("legal.manage"), request: Request,
                             db: DB):
    from app.services import legal as legal_svc

    d = await db.get(LegalDocument, doc_id)
    if d is None:
        raise NotFound("Document")
    if d.status != "draft":
        raise AppError("published_immutable", "Published versions can't be edited. Create a new version.", 409)
    if data.document_type != d.document_type:
        raise AppError("bad_request", "The document type can't change.", 400)
    for k, v in data.model_dump().items():
        setattr(d, k, v)
    audit(db, admin.id, "legal.draft_updated", request=request, target_type="legal_document", target_id=str(d.id))
    await db.commit()
    return legal_svc.doc_out(d, content=True)


@router.post("/legal/{doc_id}/publish")
async def publish_legal(doc_id: uuid.UUID, admin: Staff("legal.manage"), request: Request, db: DB):
    """Publish a draft. The previous version is archived (kept, still viewable). If the new version requires
    acceptance, every signed-in teacher is asked to accept it before continuing."""
    from app.services import legal as legal_svc

    d = await db.get(LegalDocument, doc_id)
    if d is None:
        raise NotFound("Document")
    if d.status != "draft":
        raise AppError("not_draft", "Only drafts can be published.", 409)
    previous = await legal_svc.current(db, d.document_type)
    now = utcnow()
    d.status, d.published_at = "published", now
    d.effective_from = d.effective_from or now
    if previous and d.effective_from <= now:
        previous.status = "archived"
    if d.requires_acceptance or d.document_type in ("terms", "privacy"):
        from app.services.notifications import send

        teachers = (await db.execute(select(User).where(User.status == "active", User.role != "admin"))).scalars().all()
        for t in teachers:
            await send(db, t, "legal_updated", dedupe_key=f"legal:{d.id}", title=d.title, type=d.document_type,
                       summary=d.summary_of_changes or "Please review the new version.")
    audit(db, admin.id, "legal.published", request=request, target_type="legal_document", target_id=str(d.id),
          before={"version": previous.version} if previous else None,
          after={"type": d.document_type, "version": d.version, "requires_acceptance": d.requires_acceptance})
    await db.commit()
    return legal_svc.doc_out(d)


# --------------------------------------------------------------------------- product analytics


@router.get("/analytics/events")
async def analytics_events(_: Staff("analytics.view"), db: DB, days: int = 30):
    """Counts of product events per day (sign-ups, trials, generations, checkouts…)."""
    since = utcnow() - timedelta(days=max(1, min(days, 365)))
    day = func.date_trunc("day", AnalyticsEvent.created_at)
    rows = (await db.execute(select(day, AnalyticsEvent.name, func.count(), func.count(func.distinct(
        AnalyticsEvent.user_id))).where(AnalyticsEvent.created_at >= since).group_by(day, AnalyticsEvent.name)
        .order_by(day))).all()
    totals: dict[str, dict[str, int]] = {}
    for _d, name, n, users in rows:
        t = totals.setdefault(name, {"count": 0, "users": 0})
        t["count"] += n
        t["users"] = max(t["users"], users)
    funnel_names = ("signup", "trial_started", "project_created", "lesson_generated", "checkout_started",
                    "subscription_activated")
    funnel = []
    for name in funnel_names:
        users = (await db.execute(select(func.count(func.distinct(AnalyticsEvent.user_id))).where(
            AnalyticsEvent.name == name, AnalyticsEvent.created_at >= since))).scalar_one()
        funnel.append({"step": name, "users": users})
    return {"days": [{"day": d.date().isoformat(), "name": name, "count": n} for d, name, n, _u in rows],
            "totals": totals, "funnel": funnel}


# --------------------------------------------------------------------------- API usage & AI cost dashboard


def _pct(col, p: float):
    return func.percentile_cont(p).within_group(col)


@router.get("/api-usage")
async def api_usage(_: Staff("api_usage.view"), db: DB, days: int = 7, route: str | None = None,
                    user_id: uuid.UUID | None = None, status: str | None = None):
    """Requests per day/route/user with latency percentiles, error and rate-limit counts, plus AI calls, tokens,
    cost and failures per provider/model. Filters narrow the request statistics."""
    since = utcnow() - timedelta(days=max(1, min(days, 90)))
    conds = [ApiRequest.created_at >= since]
    if route:
        conds.append(ApiRequest.route == route)
    if user_id:
        conds.append(ApiRequest.user_id == user_id)
    if status == "error":
        conds.append(ApiRequest.status >= 500)
    elif status == "client_error":
        conds.append(and_(ApiRequest.status >= 400, ApiRequest.status < 500))
    elif status == "rate_limited":
        conds.append(ApiRequest.status == 429)
    dur = ApiRequest.duration_ms
    errors = func.count().filter(ApiRequest.status >= 500)
    tot = (await db.execute(select(func.count(), errors, func.count().filter(ApiRequest.status.between(400, 499)),
                                   func.count().filter(ApiRequest.status == 429), func.avg(dur), _pct(dur, 0.5),
                                   _pct(dur, 0.95), _pct(dur, 0.99)).where(*conds))).one()
    day = func.date_trunc("day", ApiRequest.created_at)
    per_day = (await db.execute(select(day, func.count(), errors, _pct(dur, 0.95)).where(*conds).group_by(day)
                                .order_by(day))).all()
    by_route = (await db.execute(select(ApiRequest.method, ApiRequest.route, func.count(), errors, func.avg(dur),
                                        _pct(dur, 0.95), _pct(dur, 0.99)).where(*conds)
                                 .group_by(ApiRequest.method, ApiRequest.route).order_by(func.count().desc())
                                 .limit(40))).all()
    by_user = (await db.execute(select(ApiRequest.user_id, func.count(), errors,
                                       func.count().filter(ApiRequest.status == 429)).where(
        *conds, ApiRequest.user_id.is_not(None)).group_by(ApiRequest.user_id).order_by(func.count().desc())
        .limit(20))).all()
    emails = await _emails(db, [r[0] for r in by_user])

    ai_since = [AIUsage.created_at >= since] + ([AIUsage.owner_id == user_id] if user_id else [])
    aday = func.date_trunc("day", AIUsage.created_at)
    ai_day = (await db.execute(select(aday, func.count(), func.count().filter(AIUsage.success.is_(False)),
                                      func.coalesce(func.sum(AIUsage.cost_usd), 0),
                                      func.coalesce(func.sum(AIUsage.input_tokens), 0),
                                      func.coalesce(func.sum(AIUsage.output_tokens), 0)).where(*ai_since)
                               .group_by(aday).order_by(aday))).all()
    ai_models = (await db.execute(select(AIUsage.provider, AIUsage.model, func.count(),
                                         func.count().filter(AIUsage.success.is_(False)),
                                         func.coalesce(func.sum(AIUsage.cost_usd), 0), func.avg(AIUsage.latency_ms),
                                         _pct(AIUsage.latency_ms, 0.95),
                                         func.coalesce(func.sum(AIUsage.input_tokens + AIUsage.output_tokens), 0))
                                  .where(*ai_since).group_by(AIUsage.provider, AIUsage.model)
                                  .order_by(func.sum(AIUsage.cost_usd).desc()))).all()
    ai_errors = (await db.execute(select(AIUsage.error_code, func.count()).where(
        *ai_since, AIUsage.success.is_(False)).group_by(AIUsage.error_code))).all()
    spenders = (await db.execute(select(AIUsage.owner_id, func.count(), func.coalesce(func.sum(AIUsage.cost_usd), 0))
                                 .where(*ai_since, AIUsage.owner_id.is_not(None)).group_by(AIUsage.owner_id)
                                 .order_by(func.sum(AIUsage.cost_usd).desc()).limit(15))).all()
    emails.update(await _emails(db, [r[0] for r in spenders]))

    def ms(v) -> int | None:
        return int(v) if v is not None else None

    return {
        "totals": {"requests": tot[0], "server_errors": tot[1], "client_errors": tot[2], "rate_limited": tot[3],
                   "error_rate": round(tot[1] / tot[0], 4) if tot[0] else 0, "avg_ms": ms(tot[4]),
                   "p50_ms": ms(tot[5]), "p95_ms": ms(tot[6]), "p99_ms": ms(tot[7])},
        "per_day": [{"day": d.date().isoformat(), "requests": n, "errors": e, "p95_ms": ms(p)}
                    for d, n, e, p in per_day],
        "by_route": [{"method": m, "route": r, "requests": n, "errors": e, "avg_ms": ms(a), "p95_ms": ms(p95),
                      "p99_ms": ms(p99)} for m, r, n, e, a, p95, p99 in by_route],
        "by_user": [{"user_id": str(u), "email": emails.get(u), "requests": n, "errors": e, "rate_limited": rl}
                    for u, n, e, rl in by_user],
        "ai": {
            "per_day": [{"day": d.date().isoformat(), "calls": n, "failures": f, "cost_usd": round(float(c), 4),
                         "input_tokens": int(i), "output_tokens": int(o)} for d, n, f, c, i, o in ai_day],
            "by_model": [{"provider": p, "model": m, "calls": n, "failures": f, "cost_usd": round(float(c), 4),
                          "avg_ms": ms(a), "p95_ms": ms(p95), "tokens": int(t)} for p, m, n, f, c, a, p95, t in ai_models],
            "errors": [{"code": c or "error", "count": n} for c, n in ai_errors],
            "top_spenders": [{"user_id": str(u), "email": emails.get(u), "calls": n, "cost_usd": round(float(c), 4)}
                             for u, n, c in spenders],
        },
    }


# --------------------------------------------------------------------------- system health


@router.get("/system/health")
async def system_health(_: Staff("system.logs.view"), db: DB):
    from app.api.routes.platform import ready
    from app.models import ProviderHealth

    now = utcnow()
    readiness = json.loads((await ready()).body)
    jobs = dict((await db.execute(select(GenerationJob.status, func.count()).where(
        GenerationJob.created_at >= now - timedelta(days=1)).group_by(GenerationJob.status))).all())
    oldest = (await db.execute(select(func.min(GenerationJob.created_at)).where(GenerationJob.status == "queued"))
              ).scalar()
    emails = dict((await db.execute(select(EmailOutbox.status, func.count()).where(
        EmailOutbox.created_at >= now - timedelta(days=7)).group_by(EmailOutbox.status))).all())
    hooks = dict((await db.execute(select(WebhookEvent.status, func.count()).where(
        WebhookEvent.created_at >= now - timedelta(days=7)).group_by(WebhookEvent.status))).all())
    hour = now - timedelta(hours=1)
    req_total, req_err = (await db.execute(select(func.count(), func.count().filter(ApiRequest.status >= 500))
                                           .where(ApiRequest.created_at >= hour))).one()
    providers = (await db.execute(select(ProviderHealth))).scalars().all()
    critical = (await db.execute(select(func.count()).select_from(SecurityEvent).where(
        SecurityEvent.severity == "critical", SecurityEvent.created_at >= now - timedelta(days=1)))).scalar_one()
    return {
        "ready": readiness,
        "queue": {"last_24h": jobs, "queued_now": (await db.execute(select(func.count()).select_from(GenerationJob)
                                                                    .where(GenerationJob.status == "queued"))).scalar_one(),
                  "oldest_queued_minutes": int((now - oldest).total_seconds() // 60) if oldest else 0},
        "emails_7d": emails,
        "webhooks_7d": hooks,
        "api_last_hour": {"requests": req_total, "server_errors": req_err,
                          "error_rate": round(req_err / req_total, 4) if req_total else 0},
        "providers": [{"provider": p.provider, "failures": p.failures, "successes": p.successes,
                       "circuit_open": bool(p.open_until and p.open_until > now), "open_until": _iso(p.open_until),
                       "last_error": (p.last_error or "")[:300], "avg_latency_ms": int(p.avg_latency_ms or 0),
                       "updated_at": _iso(p.updated_at)} for p in providers],
        "critical_security_events_24h": critical,
    }


# --------------------------------------------------------------------------- admin push composer
from app.services.push_campaigns import CampaignIn  # noqa: E402


@router.post('/push-campaigns/preview')
async def preview_push_campaign(data: CampaignIn, _: Staff('announcements.manage'), db: DB):
    from app.services.push_campaigns import preview

    return await preview(db, data)


@router.post('/push-campaigns', status_code=202)
async def send_push_campaign(data: CampaignIn, admin: Staff('announcements.manage'), request: Request, db: DB):
    from app.jobs.queue import enqueue
    from app.services.push_campaigns import preview

    summary = await preview(db, data)
    if not summary['configured']:
        raise AppError('push_unconfigured', 'Configure Web Push keys before sending.', 409)
    if not summary['devices']:
        raise AppError('no_recipients', 'No opted-in devices match this audience.', 400)
    await usage.lock_user(db, admin.id)
    job = await enqueue(db, 'admin_push_campaign', data.model_dump(mode='json'), owner_id=admin.id, dedupe=True)
    audit(db, admin.id, 'push_campaign.queued', request=request, target_type='push_campaign', target_id=str(job.id),
          after={**data.model_dump(mode='json'), 'eligible_devices': summary['devices']})
    await db.commit()
    return {'job_id': str(job.id), **summary}


@router.get('/push-campaigns')
async def push_campaign_history(_: Staff('announcements.manage'), db: DB):
    from app.models.push import PushDelivery
    from app.services.push import push_configured

    jobs = list((await db.execute(select(GenerationJob).where(GenerationJob.type == 'admin_push_campaign')
                                 .order_by(GenerationJob.created_at.desc()).limit(50))).scalars())
    keys = [f'admin-push:{job.id}' for job in jobs]
    rows = (await db.execute(select(PushDelivery.dedupe_key, PushDelivery.status, func.count())
                            .where(PushDelivery.dedupe_key.in_(keys))
                            .group_by(PushDelivery.dedupe_key, PushDelivery.status))).all()
    counts = {}
    for key, status, count in rows:
        counts.setdefault(key, {})[status] = count
    return {'configured': push_configured(), 'items': [{
        'id': str(job.id), 'title': job.payload.get('title'), 'body': job.payload.get('body'),
        'audience': job.payload.get('audience'), 'status': job.status, 'created_at': job.created_at.isoformat(),
        'delivery': counts.get(f'admin-push:{job.id}', {}), 'error': job.error, 'queued_devices': (job.result or {}).get('queued_devices'),
    } for job in jobs]}


@router.get('/push-campaigns/recipients')
async def push_recipient_search(_: Staff('announcements.manage'), db: DB, q: str = Query('', max_length=100)):
    query = select(User).where(User.status == 'active')
    if q.strip():
        pattern = '%' + q.strip().replace('%', '').replace('_', '') + '%'
        query = query.where(or_(User.name.ilike(pattern), User.email.ilike(pattern)))
    rows = (await db.execute(query.order_by(User.name, User.id).limit(30))).scalars()
    return {'items': [{'id': str(user.id), 'name': user.name, 'email': user.email} for user in rows]}
