"""WhatsApp Business Platform (official Cloud API) integration.

Cost-aware design (utility templates are billed per message from Oct 2026):
- ONE consolidated morning template with quick-reply buttons; details go out as free-form replies inside the
  24-hour service window the teacher's tap opens.
- Opt-in is proven by the teacher sending "LINK <code>" from their phone (no verification template needed).
- STOP / START keywords, quiet hours, per-plan message limits, every message logged with its category.
Without credentials the service runs in "simulated" mode: messages are recorded but not sent.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_sessionmaker, utcnow
from app.core.errors import AppError
from app.core.logging import log
from app.core.security import create_magic_token, random_code
from app.models import Lesson, User, WhatsAppContact, WhatsAppMessage
from app.services import usage

logger = logging.getLogger("whatsapp")
E164 = re.compile(r"^\+[1-9]\d{7,14}$")

TEMPLATES = {
    "daily_plan_morning": {"category": "utility", "language": "en",
                           "body": "Good morning {{1}} 👋 You have {{2}} class(es) today: {{3}}. Your materials are "
                                   "ready.", "buttons": ["Show details", "Open today"]},
    "tomorrow_ready": {"category": "utility", "language": "en",
                       "body": "Hi {{1}}, tomorrow's lessons ({{2}}) are prepared.", "buttons": ["Show details"]},
    "reflection_checkin": {"category": "utility", "language": "en",
                           "body": "How did {{1}} go today?", "buttons": ["Went well", "Ran out of time",
                                                                          "Struggled"]},
    "job_complete": {"category": "utility", "language": "en",
                     "body": "Your {{1}} is ready: {{2}}", "buttons": []},
}


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"[^\d+]", "", raw or "")
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if digits.startswith("05") and len(digits) == 10:  # UAE mobile, local format
        digits = "+971" + digits[1:]
    if not digits.startswith("+"):
        digits = "+" + digits
    if not E164.match(digits):
        raise AppError("bad_phone", "Enter a valid mobile number in international format, e.g. +971 50 123 4567.",
                       400)
    return digits


def verify_signature(raw_body: bytes, header: str | None) -> bool:
    secret = get_settings().whatsapp_app_secret
    if not secret:
        return get_settings().environment != "production"
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[7:])


def _in_quiet_hours(contact: WhatsAppContact, now_local: datetime) -> bool:
    t = now_local.strftime("%H:%M")
    start, end = contact.quiet_start, contact.quiet_end
    return (start <= t or t < end) if start > end else (start <= t < end)


def _deep_link(user_id: uuid.UUID, path: str) -> str:
    s = get_settings()
    return f"{s.public_web_url}/auth/magic?token={create_magic_token(user_id, path, minutes=12 * 60)}"


class WhatsAppClient:
    def __init__(self) -> None:
        s = get_settings()
        self.enabled = bool(s.whatsapp_token and s.whatsapp_phone_number_id)
        self.url = f"https://graph.facebook.com/{s.whatsapp_graph_version}/{s.whatsapp_phone_number_id}/messages"
        self.token = s.whatsapp_token

    async def send(self, payload: dict[str, Any]) -> tuple[str | None, str | None]:
        if not self.enabled:
            return f"sim-{uuid.uuid4().hex[:16]}", None
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(self.url, json={"messaging_product": "whatsapp", **payload},
                                 headers={"Authorization": f"Bearer {self.token}"})
            data = r.json()
            if r.status_code >= 400:
                return None, (data.get("error") or {}).get("message", f"HTTP {r.status_code}")
            return data["messages"][0]["id"], None
        except (httpx.HTTPError, KeyError, ValueError) as e:
            return None, str(e)


async def _log(db: AsyncSession, *, user_id: uuid.UUID | None, direction: str, body: str, template: str | None,
               category: str, wa_id: str | None, status: str, error: str | None = None,
               payload: dict | None = None) -> WhatsAppMessage:
    msg = WhatsAppMessage(user_id=user_id, direction=direction, body=body[:4000], template=template, category=category,
                          wa_message_id=wa_id, status=status, error=error, payload=payload or {})
    db.add(msg)
    await db.flush()
    return msg


def _window_open(contact: WhatsAppContact) -> bool:
    return bool(contact.last_inbound_at and utcnow() - contact.last_inbound_at < timedelta(hours=23, minutes=50))


async def send_text(db: AsyncSession, contact: WhatsAppContact, text: str,
                    buttons: list[tuple[str, str]] | None = None) -> WhatsAppMessage:
    """Free-form (session) message - only valid inside the 24h customer-service window."""
    if not _window_open(contact):
        raise AppError("window_closed", "Outside the 24-hour window; use a template.", 409)
    client = WhatsAppClient()
    if buttons:
        payload = {"to": contact.phone_e164, "type": "interactive", "interactive": {
            "type": "button", "body": {"text": text[:1024]},
            "action": {"buttons": [{"type": "reply", "reply": {"id": bid, "title": title[:20]}}
                                   for bid, title in buttons[:3]]}}}
    else:
        payload = {"to": contact.phone_e164, "type": "text", "text": {"body": text[:4096], "preview_url": True}}
    wa_id, err = await client.send(payload)
    status = "failed" if err else ("sent" if client.enabled else "simulated")
    return await _log(db, user_id=contact.user_id, direction="out", body=text, template=None, category="service",
                      wa_id=wa_id, status=status, error=err, payload=payload)


async def send_template(db: AsyncSession, user: User, contact: WhatsAppContact, name: str, params: list[str],
                        button_payloads: list[str] | None = None) -> WhatsAppMessage | None:
    tpl = TEMPLATES[name]
    try:
        await usage.check(db, user, "whatsapp_messages", 1)
    except AppError:
        log(logger, logging.INFO, "whatsapp_limit_reached", user=str(user.id))
        return None
    components: list[dict[str, Any]] = [{"type": "body", "parameters": [{"type": "text", "text": p[:900]}
                                                                        for p in params]}]
    for i, pl in enumerate(button_payloads or []):
        components.append({"type": "button", "sub_type": "quick_reply", "index": str(i),
                           "parameters": [{"type": "payload", "payload": pl}]})
    payload = {"to": contact.phone_e164, "type": "template",
               "template": {"name": name, "language": {"code": tpl["language"]}, "components": components}}
    client = WhatsAppClient()
    wa_id, err = await client.send(payload)
    body = tpl["body"]
    for i, p in enumerate(params, start=1):
        body = body.replace(f"{{{{{i}}}}}", p)
    status = "failed" if err else ("sent" if client.enabled else "simulated")
    msg = await _log(db, user_id=user.id, direction="out", body=body, template=name, category=tpl["category"],
                     wa_id=wa_id, status=status, error=err, payload=payload)
    if not err:
        await usage.consume(db, user.id, 1, f"whatsapp:{name}", resource="whatsapp_messages")
    return msg


# --------------------------------------------------------------------------- linking


async def start_link(db: AsyncSession, user: User, phone: str) -> dict[str, Any]:
    plan, _ = await usage.get_plan(db, user)
    if not plan.limits.get("whatsapp_messages") and user.role != "admin":
        raise AppError("upgrade_required", "WhatsApp is included in the Genie Assistant plan. Upgrade to use it.", 402)
    phone = normalize_phone(phone)
    taken = (await db.execute(select(WhatsAppContact).where(WhatsAppContact.phone_e164 == phone,
                                                              WhatsAppContact.user_id != user.id))).scalars().first()
    if taken:
        raise AppError("phone_in_use", "This number is linked to another account.", 409)
    contact = (await db.execute(select(WhatsAppContact).where(WhatsAppContact.user_id == user.id))).scalars().first()
    code = random_code(6)
    if contact is None:
        contact = WhatsAppContact(user_id=user.id, phone_e164=phone)
        db.add(contact)
    contact.phone_e164, contact.verification_code, contact.verified, contact.opted_in = phone, code, False, False
    await db.commit()
    return {"phone": phone, "code": code, "instructions": f"Send “LINK {code}” to our WhatsApp number from {phone}."}


# --------------------------------------------------------------------------- inbound


async def handle_webhook(db: AsyncSession, body: dict[str, Any]) -> int:
    handled = 0
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for st in value.get("statuses", []):
                msg = (await db.execute(select(WhatsAppMessage).where(WhatsAppMessage.wa_message_id == st.get("id")))
                       ).scalars().first()
                if msg:
                    msg.status = st.get("status", msg.status)
                    if st.get("errors"):
                        msg.error = str(st["errors"])[:1000]
                    pricing = st.get("pricing") or {}
                    if pricing.get("category"):
                        msg.category = pricing["category"]
                handled += 1
            for m in value.get("messages", []):
                await handle_inbound(db, m)
                handled += 1
    await db.commit()
    return handled


def _inbound_text(m: dict[str, Any]) -> tuple[str, str | None]:
    t = m.get("type")
    if t == "text":
        return m["text"]["body"], None
    if t == "button":
        return m["button"].get("text", ""), m["button"].get("payload")
    if t == "interactive":
        it = m["interactive"]
        reply = it.get("button_reply") or it.get("list_reply") or {}
        return reply.get("title", ""), reply.get("id")
    return "", None


async def handle_inbound(db: AsyncSession, m: dict[str, Any]) -> None:
    if not m.get("id"):
        return
    phone = "+" + m.get("from", "").lstrip("+")
    text, payload = _inbound_text(m)
    if m.get("id") and (await db.execute(select(WhatsAppMessage.id).where(
            WhatsAppMessage.wa_message_id == m["id"]))).first():
        return  # duplicate delivery (Meta retries webhooks)
    try:
        await _log(db, user_id=None, direction="in", body=text, template=None, category="service",
                   wa_id=m.get("id"), status="received", payload=m)
    except IntegrityError:
        await db.rollback()
        return
    contact = (await db.execute(select(WhatsAppContact).where(WhatsAppContact.phone_e164 == phone))).scalars().first()
    upper = text.strip().upper()
    if contact is None:
        return  # unknown number: never message people who haven't linked an account
    contact.last_inbound_at = utcnow()
    user = await db.get(User, contact.user_id)
    last = (await db.execute(select(WhatsAppMessage).where(WhatsAppMessage.wa_message_id == m.get("id")))
            ).scalars().first()
    if last:
        last.user_id = user.id
    if upper.startswith("LINK"):
        code = upper.replace("LINK", "").strip()
        if contact.verification_code and code == contact.verification_code:
            contact.verified, contact.opted_in, contact.opted_in_at = True, True, utcnow()
            contact.verification_code = None
            from app.models import Consent

            db.add(Consent(user_id=user.id, kind="whatsapp", granted=True))
            await send_text(db, contact, f"You're connected, {user.name.split(' ')[0] or 'teacher'} ✅ I'll send your "
                                         "plan each school morning. Reply STOP any time to pause.")
        else:
            await send_text(db, contact, "That code didn't match. Please check the code in the app and try again.")
        return
    if not contact.verified:
        return
    if upper in ("STOP", "UNSUBSCRIBE", "توقف"):
        contact.opted_in = False
        await send_text(db, contact, "Paused. You won't get daily messages. Reply START to turn them back on.")
        return
    if upper in ("START", "RESUME"):
        contact.opted_in, contact.opted_in_at = True, utcnow()
        await send_text(db, contact, "Welcome back! Daily plans are on again.")
        return
    if m.get("type") == "audio" and contact.opted_in and user.status == "active":
        from app.jobs.queue import enqueue

        media_id = (m.get("audio") or {}).get("id")
        if not media_id or not str(media_id).isdigit():
            await send_text(db, contact, "That voice note could not be read. Please send it again.")
            return
        await enqueue(db, "whatsapp_voice", {"media_id": str(media_id), "message_id": m["id"]},
                      owner_id=user.id, dedupe=True)
        await send_text(db, contact, "Voice note received. I’ll read your request and prepare the materials in the background.")
        return
    if payload and payload.startswith("REFLECT:"):
        _, lesson_id, outcome = payload.split(":", 2)
        from app.services.planner import record_reflection

        res = await record_reflection(db, user, uuid.UUID(lesson_id), outcome, channel="whatsapp")
        await send_text(db, contact, "Thanks! " + (" ".join(res["effects"]) or "Noted for next time."))
        return
    if payload in ("SHOW_TODAY", "SHOW_TOMORROW") or upper in ("SHOW DETAILS", "DETAILS"):
        await send_today_details(db, user, contact, tomorrow=payload == "SHOW_TOMORROW")
        return
    if upper == "OPEN TODAY" or payload == "OPEN_TODAY":
        await send_text(db, contact, f"Here's today: {_deep_link(user.id, '/dashboard')}")
        return
    from app.services.assistant import answer_once

    reply, actions, _ = await answer_once(db, user, text)
    links = [f"{a['label']}: {_deep_link(user.id, a['href'])}" for a in actions if a.get("type") == "open"]
    reply = re.sub(r"\*\*(.+?)\*\*", r"*\1*", reply)  # markdown bold -> WhatsApp bold
    await send_text(db, contact, (reply + ("\n\n" + "\n".join(links) if links else ""))[:4000])


async def today_summary(db: AsyncSession, user: User, day) -> tuple[list[dict[str, Any]], str]:
    from app.services.planner import build_days

    plan = (await build_days(db, user, [day]))[0]
    classes = [c for c in plan["classes"]]
    short = ", ".join(f"{c['class']['name']} {c['course']['topic'] if c.get('course') else c['class']['subject']}"
                      for c in classes) or "no classes"
    return classes, short


async def send_today_details(db: AsyncSession, user: User, contact: WhatsAppContact, tomorrow: bool = False) -> None:
    from app.services.planner import next_working_day, today_for

    day = today_for(user)
    if tomorrow:
        day = await next_working_day(db, user, day)
    classes, _ = await today_summary(db, user, day)
    if not classes:
        await send_text(db, contact, "No classes on your timetable for that day.")
        return
    lines = [f"*{day.strftime('%A %d %b')}*"]
    for c in classes:
        les = c.get("lesson")
        if les:
            mats = les["materials"]
            ticks = " ".join(f"✓ {k}" for k, ok in (("Slides", mats["pptx"]), ("Plan", mats["lesson_plan"]),
                                                     ("Quiz", "quiz" in mats["documents"]),
                                                     ("Homework", "homework" in mats["documents"])) if ok)
            link = _deep_link(user.id, f"/lessons/{les['id']}")
            lines.append(f"\n*{c['start']} {c['class']['name']} {c['class']['subject']}* — {c['minutes']} min\n"
                         f"{c['course']['topic']}: L{les['number']} {les['title']}\n{ticks}\n{link}")
        else:
            lines.append(f"\n*{c['start']} {c['class']['name']}* — nothing planned yet.")
    await send_text(db, contact, "\n".join(lines))


# --------------------------------------------------------------------------- scheduler (called by the worker)


SCHEDULER_LOCK_KEY = 0x7EAC4E5  # arbitrary constant shared by all workers


async def scheduler_tick() -> dict[str, int]:
    from app.services.planner import today_for, working_days

    sent = {"daily": 0, "reflection": 0}
    async with get_sessionmaker()() as db:
        # Several workers may run the scheduler; the transaction-scoped advisory lock lets only one tick send
        # messages at a time, so nobody gets the same morning plan twice.
        if not (await db.execute(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": SCHEDULER_LOCK_KEY})).scalar():
            return sent
        contacts = (await db.execute(select(WhatsAppContact).where(WhatsAppContact.verified.is_(True),
                                                                     WhatsAppContact.opted_in.is_(True)))
                    ).scalars().all()
        for contact in contacts:
            user = await db.get(User, contact.user_id)
            if user is None or user.status != "active":
                continue
            now_local = datetime.now(ZoneInfo(user.timezone or "Asia/Dubai"))
            today = today_for(user)
            if today.weekday() not in await working_days(db, user) or _in_quiet_hours(contact, now_local):
                continue
            hhmm = now_local.strftime("%H:%M")
            if hhmm >= contact.daily_time and contact.last_daily_sent_on != today:
                classes, short = await today_summary(db, user, today)
                contact.last_daily_sent_on = today
                if classes:
                    await send_template(db, user, contact, "daily_plan_morning",
                                        [user.name.split(" ")[0] or "teacher", str(len(classes)), short[:500]],
                                        ["SHOW_TODAY", "OPEN_TODAY"])
                    sent["daily"] += 1
            if hhmm >= contact.reflection_time and contact.last_reflection_sent_on != today:
                contact.last_reflection_sent_on = today
                lesson = (await db.execute(select(Lesson).where(Lesson.owner_id == user.id,
                                                                Lesson.scheduled_date == today,
                                                                Lesson.status == "generated")
                                           .order_by(Lesson.updated_at))).scalars().first()
                if lesson:
                    await send_template(db, user, contact, "reflection_checkin", [f"“{lesson.title}”"],
                                        [f"REFLECT:{lesson.id}:went_well", f"REFLECT:{lesson.id}:ran_out_of_time",
                                         f"REFLECT:{lesson.id}:struggled"])
                    sent["reflection"] += 1
        await db.commit()
    return sent
