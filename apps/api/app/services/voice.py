"""WhatsApp voice processing runs only in the durable worker queue."""
from __future__ import annotations

from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select

from app.ai.service import get_ai
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.jobs.queue import JobContext, PermanentJobError
from app.models import User, WhatsAppContact, WhatsAppMessage
from app.services import assistant, whatsapp


class VoiceDeckRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=300)
    subject: str = Field(min_length=1, max_length=80)
    grade: str = Field(min_length=1, max_length=20)
    slides_per_lecture: int = Field(default=10, ge=4, le=30)
    num_lectures: int = Field(default=1, ge=1, le=30)
    lecture_minutes: int = Field(default=45, ge=15, le=180)


MAX_AUDIO_BYTES = 10 * 1024 * 1024
AUDIO_TYPES = {"audio/ogg": "note.ogg", "audio/mpeg": "note.mp3", "audio/mp4": "note.m4a",
               "audio/aac": "note.aac", "audio/amr": "note.amr", "audio/wav": "note.wav"}


def trusted_media_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return (parsed.scheme == "https" and parsed.port in (None, 443) and not parsed.username
            and (host == "fbsbx.com" or host.endswith(".fbsbx.com")
                 or host == "facebook.com" or host.endswith(".facebook.com")))


async def download_audio(media_id: str) -> tuple[bytes, str]:
    settings = get_settings()
    headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        response = await client.get(f"https://graph.facebook.com/{settings.whatsapp_graph_version}/{media_id}", headers=headers)
        response.raise_for_status()
        metadata = response.json()
        url = metadata.get("url", "")
        mime = metadata.get("mime_type", "").split(";", 1)[0]
        if not trusted_media_url(url) or mime not in AUDIO_TYPES:
            raise PermanentJobError("Unsupported voice note")
        if int(metadata.get("file_size", 0)) > MAX_AUDIO_BYTES:
            raise PermanentJobError("Voice note is too large")
        audio = bytearray()
        async with client.stream("GET", url, headers=headers) as stream:
            stream.raise_for_status()
            async for part in stream.aiter_bytes():
                audio.extend(part)
                if len(audio) > MAX_AUDIO_BYTES:
                    raise PermanentJobError("Voice note is too large")
        if not audio:
            raise PermanentJobError("Voice note is empty")
        return bytes(audio), AUDIO_TYPES[mime]


async def handle(ctx: JobContext) -> dict[str, str]:
    async with get_sessionmaker()() as db:
        user = await db.get(User, ctx.owner_id)
        contact = (await db.execute(select(WhatsAppContact).where(
            WhatsAppContact.user_id == ctx.owner_id))).scalars().first()
        if not user or user.status != "active" or not contact or not contact.verified or not contact.opted_in:
            raise PermanentJobError("WhatsApp is no longer enabled for this account")
    await ctx.progress(10, "Reading your voice note")
    async with get_sessionmaker()() as db:
        inbound = (await db.execute(select(WhatsAppMessage).where(
            WhatsAppMessage.wa_message_id == ctx.payload["message_id"],
            WhatsAppMessage.user_id == ctx.owner_id))).scalars().first()
        transcript = (inbound.payload or {}).get("voice_transcript") if inbound else None
    if not transcript:
        audio, filename = await download_audio(ctx.payload["media_id"])
        transcript = await get_ai().transcribe(audio, filename=filename, owner_id=ctx.owner_id, job_id=ctx.job_id)
        async with get_sessionmaker()() as db:
            inbound = (await db.execute(select(WhatsAppMessage).where(
                WhatsAppMessage.wa_message_id == ctx.payload["message_id"],
                WhatsAppMessage.user_id == ctx.owner_id))).scalars().first()
            if inbound:
                inbound.payload = {**(inbound.payload or {}), "voice_transcript": transcript[:4000]}
                await db.commit()
    await ctx.progress(40, "Preparing your teaching request")
    async with get_sessionmaker()() as db:
        user = await db.get(User, ctx.owner_id)
        contact = (await db.execute(select(WhatsAppContact).where(
            WhatsAppContact.user_id == ctx.owner_id))).scalars().first()
        if not user or user.status != "active" or not contact or not contact.opted_in:
            raise PermanentJobError("WhatsApp is no longer enabled for this account")
        # Existing intent router extracts topic, subject, grade and counts and queues generation.
        intent = await assistant.classify(transcript[:4000], user.id)
        if intent.intent == "create_course" and intent.relevance == "teaching":
            actions = []
            if not all((intent.topic, intent.subject, intent.grade)):
                reply = "Please send the topic, subject and grade, and how many slides you need."
            else:
                try:
                    request = VoiceDeckRequest(topic=intent.topic, subject=intent.subject, grade=intent.grade,
                        slides_per_lecture=intent.slides_per_lecture or 10, num_lectures=intent.lectures or 1,
                        lecture_minutes=intent.minutes or 45)
                except ValidationError:
                    reply = "Please request 4–30 slides per lesson, 1–30 lessons, and a duration of 15–180 minutes."
                else:
                    from app.services.courses import create_course
                    course, job_id = await create_course(db, user, {**request.model_dump(), "auto_generate": True,
                        "bundle": True, "instructions": transcript[:2000], "request_key": ctx.payload["message_id"]})
                    reply = f"Preparing {request.topic} for Grade {request.grade}: {request.slides_per_lecture} slides, a lesson plan, differentiated worksheet and quiz."
                    actions = [{"type": "open", "label": "Open project", "href": f"/projects/{course.project_id}"}]
        else:
            reply, actions, _ = await assistant.answer_once(db, user, transcript[:4000])
        links = [f"{a['label']}: {whatsapp._deep_link(user.id, a['href'])}" for a in actions if a.get("type") == "open"]
        if whatsapp._window_open(contact):
            await whatsapp.send_text(db, contact, (reply + "\n" + "\n".join(links))[:4000])
        else:
            await whatsapp.send_template(db, user, contact, "job_complete", ["voice request", settings_link()])
        await db.commit()
    return {"channel": "whatsapp"}


def settings_link() -> str:
    return get_settings().public_web_url + "/activity"
