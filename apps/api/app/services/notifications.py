"""Every notification the platform sends, in one catalog, plus teacher preferences and scheduled reminders.

`send(db, user, event, **ctx)` creates the in-app notification and (per the teacher's preferences) queues the
email. Each event has a category; security, billing-problem and legal events are mandatory and can't be turned
off. Scheduled reminders (trial ending, renewals, failed-payment follow-ups, expiring granted plans) run from the
worker every hour and are de-duplicated per subscription and period, so nobody gets the same reminder twice.
Staff alerts go to every staff member whose role holds the matching permission.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_sessionmaker, utcnow
from app.core.logging import log
from app.models import Plan, Subscription, TeacherPreference, User
from app.services.notify import TEMPLATES, notify, queue_email

logger = logging.getLogger("notifications")

# category -> (label shown in settings, mandatory)
CATEGORIES: dict[str, tuple[str, bool]] = {
    "security": ("Sign-ins and account security", True),
    "billing": ("Payments, renewals and receipts", False),
    "billing_alert": ("Failed payments and plan problems", True),
    "usage": ("Credit and limit warnings", False),
    "product": ("Lessons and files ready", False),
    "support": ("Replies to your support requests", False),
    "announcement": ("Product news and maintenance notices", False),
    "legal": ("Changes to terms and policies", True),
}


@dataclass(frozen=True)
class Event:
    category: str
    title: str
    body: str
    link: str
    email: str | None = None  # template in notify.TEMPLATES
    email_default: bool = True  # emailed unless the teacher turned email off for the category


EVENTS: dict[str, Event] = {
    "task_ready": Event("product", "Ready: {title}", "Your background task is complete. Open it whenever you're ready.", "{link}"),
    "task_failed": Event("product", "Needs attention: {title}", "Your background task couldn't finish. Open Activity to review it.", "/activity"),
    # --- trial & plan
    "trial_ending": Event("billing", "Your trial ends in {days} day{s}",
                          "Choose a plan to keep your {plan} features. Your lessons stay safe either way.",
                          "/billing", "trial_ending"),
    "trial_ended": Event("billing_alert", "Your free trial has ended",
                         "You're on the Free plan now. Upgrade any time to keep building full units.",
                         "/billing", "trial_ended"),
    "renewal_upcoming": Event("billing", "Your {plan} plan renews on {date}",
                              "We'll charge {amount} to your saved payment method. Manage or cancel any time.",
                              "/billing", "renewal_upcoming"),
    "plan_ending": Event("billing", "Your {plan} plan ends on {date}",
                         "You cancelled renewal. Re-subscribe before then to keep your plan.", "/billing",
                         "plan_ending"),
    "grant_expiring": Event("billing", "Your {plan} access ends on {date}",
                            "The plan your school or our team gave you is ending. Choose a plan to continue.",
                            "/billing", "grant_expiring"),
    "payment_retry_reminder": Event("billing_alert", "Your payment is still outstanding",
                                    "We couldn't take payment for {plan} {days} days ago. Update your payment method "
                                    "to keep your plan.", "/billing", "payment_reminder"),
    "referral_reward": Event("billing", "Your referral reward is ready", "You've earned {credits} media credits. Create something for your next class.", "/billing", "referral_reward"),
    "payment_receipt": Event("billing", "Payment received: {amount}", "Thank you. Your receipt is in Plan & billing.",
                             "/billing", None),
    "media_credits_low": Event("usage", "Media credits running low",
                               "You have {balance} media credits left. Top up to keep creating images and videos.",
                               "/media", None),
    # --- product
    "lesson_ready": Event("product", "Lesson ready: {title}", "Your slides are built and ready to download.",
                          "/lessons/{id}", None),
    "lesson_failed": Event("product", "We couldn't build “{title}”",
                           "Nothing was charged. Open the lesson to try again.", "/lessons/{id}", None),
    "course_planned": Event("product", "Unit planned: {title}", "Your lesson sequence is ready to review.",
                            "/projects/{id}", None),
    "course_failed": Event("product", "We couldn't plan “{title}”", "Open your project to review the problem.", "/projects/{id}", None),
    "document_ready": Event("product", "{title} is ready", "Download it from your library.", "/lessons?tab=documents&document={id}", None),
    "document_failed": Event("product", "We couldn't create “{title}”", "Nothing was charged. Please try again.",
                             "/lessons", None),
    "media_ready": Event("product", "Your {kind} is ready", "It's in your media studio, labelled as AI-generated.",
                         "/media", None),
    "media_failed": Event("product", "Your {kind} couldn't be created", "Your media credits were refunded.",
                          "/media", None),
    # --- legal
    "legal_updated": Event("legal", "We've updated our {title}", "{summary}", "/legal/{type}", None),
}

# Staff alerts: event -> (permission that receives it, title, body, link)
STAFF_ALERTS: dict[str, tuple[str, str, str, str]] = {
    "new_ticket": ("support.manage", "New {kind} request #{number}", "{subject}", "/admin/support/{id}"),
    "payment_failed": ("billing.view", "Payment failed: {email}", "{amount} {reason}", "/admin/billing"),
    "security_critical": ("security.view", "Critical security event: {type}", "{summary}", "/admin/security"),
    "provider_down": ("system.logs.view", "AI provider circuit open: {provider}", "{error}", "/admin/system"),
    "webhook_failed": ("system.logs.view", "Webhook processing failed ({provider})", "{error}", "/admin/system"),
    "job_failures": ("system.logs.view", "{count} generation jobs failed in the last hour", "Check the job log.",
                     "/admin/system"),
}

TEMPLATES.update({
    "referral_reward": ("Your Clastio referral reward is ready", "Hi {name},\n\nYou've earned {credits} media credits after a referred teacher's first paid subscription. Use them in Media studio: {link}\n"),
    "trial_ending": ("Your Clastio trial ends in {days} day{s}",
                     "Hi {name},\n\nYour free {plan} trial ends in {days} day{s}. Choose a plan to keep everything "
                     "working; your lessons and designs are safe either way: {link}\n"),
    "trial_ended": ("Your Clastio trial has ended",
                    "Hi {name},\n\nYour free trial has ended and your account is on the Free plan. Upgrade any time: "
                    "{link}\n"),
    "renewal_upcoming": ("Your {plan} plan renews on {date}",
                         "Hi {name},\n\nThis is a reminder that your {plan} plan renews on {date} for {amount}. "
                         "Nothing to do if you'd like to continue. To change or cancel: {link}\n"),
    "plan_ending": ("Your {plan} plan ends on {date}",
                    "Hi {name},\n\nYou cancelled renewal, so your {plan} plan ends on {date}. Re-subscribe any time "
                    "before then to keep it: {link}\n"),
    "grant_expiring": ("Your {plan} access ends on {date}",
                       "Hi {name},\n\nThe {plan} access you were given ends on {date}. Choose a plan to continue: "
                       "{link}\n"),
    "payment_reminder": ("Reminder: payment needed for your Clastio plan",
                         "Hi {name},\n\nWe still couldn't take payment for your {plan} plan ({days} days ago). "
                         "Please update your payment method so your plan isn't cancelled: {link}\n"),
})


class _Safe(dict):
    def __missing__(self, key: str) -> str:
        return ""


def _fmt(text: str, ctx: dict[str, Any]) -> str:
    return text.format_map(_Safe(ctx))


# --------------------------------------------------------------------------- preferences

PREF_KEY = "notification_prefs"


def default_prefs() -> dict[str, dict[str, bool]]:
    return {c: {"in_app": True, "email": c not in ("product",)} for c in CATEGORIES}


async def get_prefs(db: AsyncSession, user_id: uuid.UUID) -> dict[str, dict[str, bool]]:
    row = (await db.execute(select(TeacherPreference).where(TeacherPreference.user_id == user_id,
                                                            TeacherPreference.key == PREF_KEY))).scalars().first()
    prefs = default_prefs()
    for cat, val in ((row.value if row else None) or {}).items():
        if cat in prefs and isinstance(val, dict):
            prefs[cat].update({k: bool(v) for k, v in val.items() if k in ("in_app", "email")})
    for cat, (_, mandatory) in CATEGORIES.items():
        if mandatory:
            prefs[cat] = {"in_app": True, "email": True}
    return prefs


async def set_prefs(db: AsyncSession, user_id: uuid.UUID, changes: dict[str, dict[str, bool]]) -> dict:
    current = await get_prefs(db, user_id)
    for cat, val in changes.items():
        if cat in current and not CATEGORIES[cat][1]:
            current[cat].update({k: bool(v) for k, v in val.items() if k in ("in_app", "email")})
    row = (await db.execute(select(TeacherPreference).where(TeacherPreference.user_id == user_id,
                                                            TeacherPreference.key == PREF_KEY))).scalars().first()
    stored = {c: v for c, v in current.items() if not CATEGORIES[c][1]}
    if row:
        row.value = stored
    else:
        db.add(TeacherPreference(user_id=user_id, key=PREF_KEY, value=stored, source="stated"))
    return current


# --------------------------------------------------------------------------- sending


async def send(db: AsyncSession, user: User, event: str, *, dedupe_key: str | None = None, **ctx: Any) -> bool:
    """In-app notification plus optional email for one catalog event. Returns True if it was new."""
    ev = EVENTS[event]
    ctx = {"s": "" if str(ctx.get("days", "")) == "1" else "s", **ctx}
    prefs = await get_prefs(db, user.id)
    cat = prefs.get(ev.category, {"in_app": True, "email": True})
    link = _fmt(ev.link, ctx)
    created = True
    if cat["in_app"] or dedupe_key:  # the dedupe row also stops a repeat email
        created = await notify(db, user.id, ev.category, _fmt(ev.title, ctx)[:200], _fmt(ev.body, ctx), link,
                               dedupe_key=dedupe_key)
    if created and ev.email and cat["email"] and ev.email_default and user.status == "active":
        queue_email(db, user, ev.email, link=f"{get_settings().public_web_url}{link}",
                    **{k: str(v) for k, v in ctx.items() if k not in ("name", "link")})
    return created


async def send_by_id(user_id: uuid.UUID | None, event: str, *, dedupe_key: str | None = None, **ctx: Any) -> None:
    """For job handlers and other code that has no session open: never raises."""
    if not user_id:
        return
    try:
        async with get_sessionmaker()() as db:
            user = await db.get(User, user_id)
            if user and user.role != "admin":
                await send(db, user, event, dedupe_key=dedupe_key, **ctx)
                await db.commit()
    except Exception as e:  # noqa: BLE001 - a notification must never break the work that triggered it
        log(logger, logging.WARNING, "notification_failed", event=event, error=str(e)[:200])


async def alert_staff(db: AsyncSession, alert: str, *, dedupe_key: str | None = None, **ctx: Any) -> int:
    """Notify every active staff member whose role includes the alert's permission."""
    from app.core.deps import staff_permissions

    perm, title, body, link = STAFF_ALERTS[alert]
    staff = (await db.execute(select(User).where(User.role == "admin", User.status == "active"))).scalars().all()
    n = 0
    for s in staff:
        if perm in staff_permissions(s):
            key = f"{dedupe_key}:{s.id}" if dedupe_key else None
            if await notify(db, s.id, "staff", _fmt(title, ctx)[:200], _fmt(body, ctx)[:1000], _fmt(link, ctx),
                            dedupe_key=key):
                n += 1
    return n


async def alert_staff_detached(alert: str, *, dedupe_key: str | None = None, **ctx: Any) -> None:
    try:
        async with get_sessionmaker()() as db:
            await alert_staff(db, alert, dedupe_key=dedupe_key, **ctx)
            await db.commit()
    except Exception as e:  # noqa: BLE001
        log(logger, logging.WARNING, "staff_alert_failed", alert=alert, error=str(e)[:200])


async def broadcast(db: AsyncSession, *, title: str, body: str, link: str | None, audience: str,
                    dedupe_key: str) -> int:
    """Put an announcement in every active account's notification list (respecting the announcement pref)."""
    q = select(User.id).where(User.status == "active")
    if audience == "teachers":
        q = q.where(User.role != "admin")
    elif audience == "staff":
        q = q.where(User.role == "admin")
    n = 0
    for uid in (await db.execute(q)).scalars().all():
        prefs = await get_prefs(db, uid)
        if prefs["announcement"]["in_app"] and await notify(db, uid, "announcement", title[:200], body, link,
                                                            dedupe_key=f"{dedupe_key}:{uid}"):
            n += 1
    return n


# --------------------------------------------------------------------------- scheduled reminders


def _money(amount: Any) -> str:
    try:
        return f"AED {float(amount):,.2f}".replace(".00", "")
    except (TypeError, ValueError):
        return "your plan price"


async def run_reminders() -> dict[str, int]:
    """Hourly worker tick. Each reminder is keyed to the subscription and its period end, so it's sent once."""
    now = utcnow()
    out = {"trial_ending": 0, "trial_ended": 0, "renewal_upcoming": 0, "plan_ending": 0, "grant_expiring": 0,
           "payment_retry_reminder": 0}
    async with get_sessionmaker()() as db:
        plans = {p.code: p for p in (await db.execute(select(Plan))).scalars().all()}
        rows = (await db.execute(select(Subscription, User).join(User, User.id == Subscription.user_id).where(
            User.status == "active", User.role != "admin",
            Subscription.current_period_end.is_not(None),
            Subscription.current_period_end > now - timedelta(days=2),
            Subscription.current_period_end < now + timedelta(days=8)))).all()
        for sub, user in rows:
            plan = plans.get(sub.plan_code)
            name = plan.name if plan else sub.plan_code
            end = sub.current_period_end
            left = (end - now).total_seconds() / 86400
            date = end.strftime("%d %b %Y")
            period = end.date().isoformat()
            live = sub.status in ("active", "trialing", "past_due")
            if sub.provider == "trial" and live:
                if 0 < left <= 3:
                    days = 1 if left <= 1 else 3
                    if await send(db, user, "trial_ending", dedupe_key=f"trial_ending:{sub.id}:{days}", days=days,
                                  plan=name):
                        out["trial_ending"] += 1
                elif left <= 0 and not await _has_newer_paid(db, sub):
                    if await send(db, user, "trial_ended", dedupe_key=f"trial_ended:{sub.id}", plan=name):
                        out["trial_ended"] += 1
            elif sub.provider in ("stripe", "dodo") and sub.status == "active" and 0 < left <= 7:
                if sub.cancel_at_period_end:
                    if left <= 3 and await send(db, user, "plan_ending", dedupe_key=f"plan_ending:{sub.id}:{period}",
                                                plan=name, date=date):
                        out["plan_ending"] += 1
                else:
                    lead = 7 if sub.interval == "year" else 3
                    price = (plan.price_annual_aed if sub.interval == "year" else plan.price_monthly_aed) if plan \
                        else None
                    if left <= lead and await send(db, user, "renewal_upcoming",
                                                   dedupe_key=f"renewal:{sub.id}:{period}", plan=name, date=date,
                                                   amount=_money(sub.price_aed or price)):
                        out["renewal_upcoming"] += 1
            elif sub.provider == "manual" and live and 0 < left <= 7:
                days = 1 if left <= 1 else 7
                if await send(db, user, "grant_expiring", dedupe_key=f"grant:{sub.id}:{days}", plan=name, date=date):
                    out["grant_expiring"] += 1
        # Dunning: follow-ups 3 and 7 days after a subscription went past due.
        overdue = (await db.execute(select(Subscription, User).join(User, User.id == Subscription.user_id).where(
            Subscription.status == "past_due", User.status == "active",
            Subscription.updated_at < now - timedelta(days=1)))).all()
        for sub, user in overdue:
            days = int((now - sub.updated_at).total_seconds() // 86400)
            step = 7 if days >= 7 else 3 if days >= 3 else 1
            plan = plans.get(sub.plan_code)
            if await send(db, user, "payment_retry_reminder", dedupe_key=f"dunning:{sub.id}:{sub.current_period_start}:{step}", days=step,
                          plan=plan.name if plan else sub.plan_code):
                out["payment_retry_reminder"] += 1
        await db.commit()
    return out


async def _has_newer_paid(db: AsyncSession, trial: Subscription) -> bool:
    return (await db.execute(select(Subscription.id).where(
        Subscription.user_id == trial.user_id, Subscription.provider.in_(("stripe", "dodo", "manual")),
        Subscription.created_at >= trial.created_at))).first() is not None


async def job_failure_watch() -> int:
    """Hourly: tell operators when generation jobs are failing in bulk."""
    from sqlalchemy import func

    from app.models import GenerationJob

    since = utcnow() - timedelta(hours=1)
    async with get_sessionmaker()() as db:
        n = (await db.execute(select(func.count()).select_from(GenerationJob).where(
            GenerationJob.status == "failed", GenerationJob.completed_at >= since))).scalar_one()
        if n >= 5:
            await alert_staff(db, "job_failures", dedupe_key=f"jobfail:{since:%Y%m%d%H}", count=n)
            await db.commit()
    return n


# --------------------------------------------------------------------------- job completion

NOTIFY_JOBS = {"lesson_generation", "course_plan", "document_generation", "media_generation",
               "style_analysis", "source_indexing", "slide_regeneration", "image_replacement", "lesson_render", "assistant_reply", "template_preview"}


async def job_finished(job_type: str, job_id: uuid.UUID, owner_id: uuid.UUID | None, payload: dict[str, Any],
                       ok: bool) -> None:
    """Tell the teacher when background work they started has finished (or failed for good)."""
    if job_type not in NOTIFY_JOBS or not owner_id:
        return
    from app.models import Course, Document, Lesson, MediaItem

    try:
        async with get_sessionmaker()() as db:
            key = f"job:{job_id}"
            if job_type == "lesson_generation":
                obj = await db.get(Lesson, uuid.UUID(payload["lesson_id"]))
                ctx, event = ({"title": obj.title, "id": str(obj.id)} if obj else None), \
                    "lesson_ready" if ok else "lesson_failed"
            elif job_type == "course_plan":
                obj = await db.get(Course, uuid.UUID(payload["course_id"]))
                ctx, event = ({"title": obj.topic, "id": str(obj.project_id)} if obj else None), "course_planned" if ok else "course_failed"
            elif job_type == "document_generation":
                obj = await db.get(Document, uuid.UUID(payload["document_id"]))
                ctx, event = ({"title": obj.title, "id": str(obj.id)} if obj else None), "document_ready" if ok else "document_failed"
            elif job_type == "media_generation":
                obj = await db.get(MediaItem, uuid.UUID(payload["media_id"]))
                ctx, event = ({"kind": obj.kind} if obj else None), "media_ready" if ok else "media_failed"
            else:
                from app.models import GenerationJob
                from app.services.activity import summaries

                job = await db.get(GenerationJob, job_id)
                item = (await summaries(db, [job]))[0] if job else None
                ctx = {"title": item["title"], "link": item["href"]} if item else None
                event = "task_ready" if ok else "task_failed"
            user = await db.get(User, owner_id)
            if ctx is None or user is None or user.role == "admin":
                return
            await send(db, user, event, dedupe_key=key, **ctx)
            await db.commit()
    except Exception as e:  # noqa: BLE001
        log(logger, logging.WARNING, "job_notification_failed", job_type=job_type, error=str(e)[:200])
