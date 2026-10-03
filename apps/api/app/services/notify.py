"""In-app notifications and queued transactional email.

Emails are written to email_outbox inside the caller's transaction and sent by the worker with retries, so a slow
or failing mail server never blocks a request. Without RESEND_API_KEY or SMTP_URL the worker logs the email instead of sending it.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import uuid
from datetime import timedelta
from email.message import EmailMessage
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_sessionmaker, utcnow
from app.core.logging import log
from app.models import EmailOutbox, Notification, User

logger = logging.getLogger("notify")

MAX_EMAIL_ATTEMPTS = 5

# template -> (subject, body). Bodies are plain text; {name}, {link} and template-specific fields are filled in.
TEMPLATES: dict[str, tuple[str, str]] = {
    "welcome": ("Welcome to Clastio",
                "Hi {name},\n\nWelcome to Clastio. Upload a deck you've taught with and your first lessons will "
                "come out in your own design.\n\nGet started: {link}\n"),
    "verify_email": ("Confirm your email for Clastio",
                     "Hi {name},\n\nPlease confirm your email address:\n{link}\n\nThis link expires in 48 hours. If "
                     "you didn't create an account, ignore this email.\n"),
    "password_reset": ("Reset your Clastio password",
                       "Hi {name},\n\nSomeone asked to reset your password. If it was you, choose a new one here:\n"
                       "{link}\n\nThe link expires in 30 minutes. If it wasn't you, ignore this email: your password "
                       "has not changed.\n"),
    "password_changed": ("Your Clastio password was changed",
                         "Hi {name},\n\nYour password was just changed and your other devices were signed out. If this "
                         "wasn't you, reset your password now: {link}\n"),
    "login_alert": ("New sign-in to Clastio",
                    "Hi {name},\n\nWe noticed a sign-in from a new device: {device} ({ip}).\n\nIf this was you, "
                    "there's nothing to do. If not, sign out that device and change your password: {link}\n"),
    "subscription_confirmed": ("You're on {plan}",
                               "Hi {name},\n\nThank you! Your {plan} plan is active. Manage it any time: {link}\n"),
    "payment_failed": ("Payment problem with your Clastio plan",
                       "Hi {name},\n\nWe couldn't take your latest payment. Please update your payment method to keep "
                       "your plan: {link}\n"),
    "subscription_cancelled": ("Your Clastio plan was cancelled",
                               "Hi {name},\n\nYour plan has been cancelled. You keep access until the end of the "
                               "period you paid for. You can re-subscribe any time: {link}\n"),
    "usage_warning": ("You've used {percent}% of your monthly credits",
                      "Hi {name},\n\nYou've used {percent}% of this month's credits on your {plan} plan. When they run "
                      "out, new lessons wait until next month unless you upgrade: {link}\n"),
    "deletion_scheduled": ("Your Clastio account will be deleted",
                           "Hi {name},\n\nYour account is scheduled for deletion on {date}. Until then you can cancel "
                           "by contacting support. After that date your content is permanently removed.\n"),
    "account_suspended": ("Your Clastio account is suspended",
                          "Hi {name},\n\nYour account has been suspended: {reason}\n\nIf you think this is a "
                          "mistake, reply to this email or contact support.\n"),
    "account_restored": ("Your Clastio account is active again",
                         "Hi {name},\n\nYour account has been restored. You can sign in again: {link}\n"),
    "ticket_reply": ("Update on your request #{number}",
                     "Hi {name},\n\nThere's a new reply on your request \"{subject}\":\n\n{reply}\n\nView it: {link}\n"),
}


def queue_email(db: AsyncSession, user: User | None, template: str, *, to: str | None = None, link: str = "",
                **fields: str) -> EmailOutbox:
    subject, body = TEMPLATES[template]
    values = {"name": (user.name.split(" ")[0] if user and user.name else "there"), "link": link, **fields}
    row = EmailOutbox(user_id=user.id if user else None, to_email=(to or (user.email if user else "")),
                      template=template, subject=subject.format(**values), body_text=body.format(**values))
    db.add(row)
    return row


async def notify(db: AsyncSession, user_id: uuid.UUID, type_: str, title: str, body: str = "", link: str | None = None,
                 dedupe_key: str | None = None) -> bool:
    """Create an in-app notification. With a dedupe_key it is created at most once. Returns True if new."""
    stmt = insert(Notification).values(id=uuid.uuid4(), user_id=user_id, type=type_, title=title, body=body,
                                       link=link, dedupe_key=dedupe_key, created_at=utcnow())
    if dedupe_key:
        stmt = stmt.on_conflict_do_nothing(index_elements=["user_id", "dedupe_key"])
    res = await db.execute(stmt)
    return bool(res.rowcount)


def _smtp_send(msg: EmailMessage) -> None:
    url = urlparse(get_settings().smtp_url or "")
    port = url.port or (465 if url.scheme == "smtps" else 587)
    cls = smtplib.SMTP_SSL if url.scheme == "smtps" else smtplib.SMTP
    with cls(url.hostname, port, timeout=20) as server:
        if url.scheme != "smtps":
            server.starttls()
        if url.username:
            server.login(url.username, url.password or "")
        server.send_message(msg)


async def send_pending_emails(limit: int = 20) -> int:
    """Worker tick: send queued emails, retrying with backoff; gives up after MAX_EMAIL_ATTEMPTS."""
    s = get_settings()
    sent = 0
    async with get_sessionmaker()() as db:
        rows = (await db.execute(select(EmailOutbox).where(EmailOutbox.status == "queued",
                                                           EmailOutbox.send_after <= utcnow())
                                 .order_by(EmailOutbox.created_at).limit(limit).with_for_update(skip_locked=True))
                ).scalars().all()
        for row in rows:
            row.attempts += 1
            if not s.smtp_url and not s.resend_api_key:
                row.status, row.sent_at, row.last_error = "logged", utcnow(), "Email provider not configured; email not sent"
                log(logger, logging.INFO, "email_logged", template=row.template, to_domain=row.to_email.split("@")[-1])
                continue
            msg = EmailMessage()
            msg["From"], msg["To"], msg["Subject"] = s.email_from, row.to_email, row.subject
            msg.set_content(row.body_text)
            try:
                if s.resend_api_key:
                    async with httpx.AsyncClient(timeout=20) as client:
                        result = await client.post(
                            "https://api.resend.com/emails",
                            headers={"Authorization": f"Bearer {s.resend_api_key}",
                                     "Idempotency-Key": f"outbox/{row.id}"},
                            json={"from": s.email_from, "to": [row.to_email],
                                  "subject": row.subject, "text": row.body_text},
                        )
                        if not result.is_success:
                            # Never persist request headers / API keys in outbox errors.
                            raise RuntimeError(f"Resend delivery failed (HTTP {result.status_code})")
                else:
                    await asyncio.to_thread(_smtp_send, msg)
                row.status, row.sent_at, row.last_error = "sent", utcnow(), None
                sent += 1
            except Exception as e:  # noqa: BLE001 - any SMTP failure is retried
                row.last_error = str(e)[:500]
                if row.attempts >= MAX_EMAIL_ATTEMPTS:
                    row.status = "failed"
                else:
                    row.send_after = utcnow() + timedelta(minutes=2 ** row.attempts)
        await db.commit()
    return sent
