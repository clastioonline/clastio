from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sse_starlette.sse import EventSourceResponse

from app.core.db import utcnow
from app.core.deps import DB, CurrentUser
from app.core.errors import AppError, NotFound
from app.core.ratelimit import rate_limit
from app.jobs.queue import enqueue, run_inline_if_configured
from app.models import Conversation, ConversationMessage, GenerationJob, TeacherMemory, TeacherPreference, Lesson, Slide
from app.services import assistant
from app.services import memory as memory_svc

router = APIRouter(tags=["assistant", "memory"])


# --------------------------------------------------------------------------- memory


@router.get("/memory")
async def get_memory(user: CurrentUser, db: DB, kind: str | None = None, limit: int = 50):
    prefs = await memory_svc.list_preferences(db, user.id)
    q = select(TeacherMemory).where(TeacherMemory.user_id == user.id)
    if kind:
        q = q.where(TeacherMemory.kind == kind)
    items = (await db.execute(q.order_by(TeacherMemory.created_at.desc()).limit(min(limit, 300)))).scalars().all()
    return {
        "preferences": [{"key": p.key, "label": memory_svc.PREFERENCE_LABELS.get(p.key, p.key.replace("_", " ")),
                         "value": p.value, "source": p.source, "confirmed": p.confirmed, "confidence": p.confidence}
                        for p in prefs],
        "items": [{"id": str(m.id), "kind": m.kind, "content": m.content, "created_at": m.created_at.isoformat(),
                   "class_section_id": str(m.class_section_id) if m.class_section_id else None} for m in items],
        "known_preferences": memory_svc.PREFERENCE_LABELS,
    }


class PrefIn(BaseModel):
    value: Any


@router.put("/memory/preferences/{key}")
async def set_pref(key: str, data: PrefIn, user: CurrentUser, db: DB):
    value = data.value
    allowed_images = {"preferred_image_style": {"photograph", "diagram", "illustration", "cartoon"},
                      "preferred_image_source": {"hybrid", "stock", "ai"}}
    if key in allowed_images:
        value = str(value).strip().lower()
        if value not in allowed_images[key]:
            raise AppError("invalid_preference", "Choose one of: " + ", ".join(sorted(allowed_images[key])), 422)
    row = await memory_svc.set_preference(db, user.id, key[:80], value, source="stated")
    await db.commit()
    return {"key": row.key, "value": row.value}


@router.post("/memory/preferences/{key}/confirm")
async def confirm_pref(key: str, user: CurrentUser, db: DB):
    row = (await db.execute(select(TeacherPreference).where(TeacherPreference.user_id == user.id,
                                                              TeacherPreference.key == key))).scalars().first()
    if row is None:
        raise NotFound("Preference")
    row.confirmed, row.source, row.confidence = True, "stated", 1.0
    await db.commit()
    return {"ok": True}


@router.delete("/memory/preferences/{key}")
async def delete_pref(key: str, user: CurrentUser, db: DB):
    await db.execute(delete(TeacherPreference).where(TeacherPreference.user_id == user.id,
                                                      TeacherPreference.key == key))
    await db.commit()
    return {"ok": True}


class MemoryIn(BaseModel):
    kind: str = Field("note", pattern="^(note|feedback|misconception)$")
    content: str = Field(min_length=2, max_length=4000)
    class_section_id: uuid.UUID | None = None


@router.post("/memory/items")
async def add_item(data: MemoryIn, user: CurrentUser, db: DB):
    m = await memory_svc.add_memory(db, user.id, data.kind, data.content, class_section_id=data.class_section_id)
    await db.commit()
    return {"id": str(m.id)}


@router.delete("/memory/items/{item_id}")
async def delete_item(item_id: uuid.UUID, user: CurrentUser, db: DB):
    m = await db.get(TeacherMemory, item_id)
    if m is None or m.user_id != user.id:
        raise NotFound("Memory")
    await db.delete(m)
    await db.commit()
    return {"ok": True}


@router.get("/memory/search")
async def search(q: str, user: CurrentUser, db: DB):
    rows = await memory_svc.search_memory(db, user.id, q, k=8)
    return {"items": [{"id": str(m.id), "kind": m.kind, "content": m.content} for m in rows]}


# --------------------------------------------------------------------------- assistant


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None
    mode: str = Field(default="assistant", pattern="^(assistant|playground|image_edit)$")
    lesson_id: uuid.UUID | None = None
    slide_number: int | None = Field(None, ge=1, le=30)


@router.post("/assistant/tasks", status_code=202, dependencies=[Depends(rate_limit("assistant", 40, 600))])
async def queue_message(data: MessageIn, user: CurrentUser, db: DB):
    from app.services import usage

    await usage.lock_user(db, user.id)
    await usage.check_generation_allowed(db, user)
    if not data.text.strip():
        raise AppError("empty_message", "Write a message first.", 422)
    if data.conversation_id:
        conv = await db.get(Conversation, data.conversation_id)
        if conv is None or conv.owner_id != user.id:
            raise NotFound("Conversation")
        pending = (await db.execute(select(GenerationJob.id).where(
            GenerationJob.owner_id == user.id, GenerationJob.type == "assistant_reply",
            GenerationJob.payload["conversation_id"].astext == str(conv.id),
            GenerationJob.status.in_(["queued", "running"])))).first()
        if pending:
            raise AppError("reply_pending", "A reply is already being prepared in this conversation.", 409)
    else:
        conv = Conversation(owner_id=user.id, title=data.text.strip()[:80],
                            channel=data.mode if data.mode in ("playground", "image_edit") else "web")
        if data.mode == "image_edit":
            lesson = await db.get(Lesson, data.lesson_id) if data.lesson_id else None
            if not lesson or lesson.owner_id != user.id or not data.slide_number:
                raise NotFound("Lesson slide")
            row = (await db.execute(select(Slide).where(Slide.lesson_id == lesson.id, Slide.number == data.slide_number))).scalars().first()
            if not row:
                raise NotFound("Slide")
            if row.spec.get("layout") not in ("image_text", "concept"):
                raise AppError("image_layout", "Choose an image or concept slide to discuss a picture replacement.", 422)
        db.add(conv)
        await db.flush()
        if data.mode == "image_edit":
            db.add(ConversationMessage(conversation_id=conv.id, role="system", content="Image change target", actions=[{
                "type": "image_target", "lesson_id": str(data.lesson_id), "slide_number": data.slide_number}]))
    conv.updated_at = utcnow()
    db.add(ConversationMessage(conversation_id=conv.id, role="user", content=data.text.strip()))
    job = await enqueue(db, "assistant_reply", {"conversation_id": str(conv.id), "text": data.text.strip()},
                        owner_id=user.id, max_attempts=1)
    await db.commit()
    await run_inline_if_configured([job.id])
    return {"conversation_id": str(conv.id), "job_id": str(job.id)}


@router.post("/assistant/messages", dependencies=[Depends(rate_limit("assistant", 40, 600))])
async def message(data: MessageIn, user: CurrentUser, db: DB):
    if data.mode == "image_edit" and not data.conversation_id:
        raise AppError("use_queue", "Start image discussions through /assistant/tasks with a lesson and slide.", 422)
    async def gen():
        async for ev in assistant.converse(db, user, data.text, data.conversation_id, mode=data.mode):
            yield {"event": ev["event"], "data": json.dumps(ev["data"])}

    return EventSourceResponse(gen())


@router.get("/assistant/conversations")
async def conversations(user: CurrentUser, db: DB):
    rows = (await db.execute(select(Conversation).where(Conversation.owner_id == user.id)
                             .order_by(Conversation.updated_at.desc()).limit(50))).scalars().all()
    return {"items": [{"id": str(c.id), "title": c.title, "updated_at": c.updated_at.isoformat()} for c in rows]}


@router.get("/assistant/conversations/{conv_id}")
async def conversation(conv_id: uuid.UUID, user: CurrentUser, db: DB):
    c = await db.get(Conversation, conv_id)
    if c is None or c.owner_id != user.id:
        raise NotFound("Conversation")
    msgs = (await db.execute(select(ConversationMessage).where(ConversationMessage.conversation_id == c.id)
                             .order_by(ConversationMessage.created_at))).scalars().all()
    job = (await db.execute(select(GenerationJob).where(GenerationJob.owner_id == user.id,
        GenerationJob.type == "assistant_reply", GenerationJob.payload["conversation_id"].astext == str(c.id))
        .order_by(GenerationJob.created_at.desc()).limit(1))).scalars().first()
    return {"id": str(c.id), "title": c.title, "mode": c.channel,
            "job": {"id": str(job.id), "status": job.status, "stage": job.stage,
                    "result": job.result} if job else None,
            "messages": [{"id": str(m.id), "role": m.role, "content": m.content, "actions": m.actions,
                          "created_at": m.created_at.isoformat()} for m in msgs if m.role != "system"]}


class ImageConfirmIn(BaseModel):
    message_id: uuid.UUID
    remember_style: bool = False


@router.post("/assistant/conversations/{conv_id}/confirm-image", status_code=202,
             dependencies=[Depends(rate_limit("image_confirmation", 20, 3600))])
async def confirm_image(conv_id: uuid.UUID, data: ImageConfirmIn, user: CurrentUser, db: DB):
    from app.services.image_assistant import confirm
    job_id = await confirm(db, user, conv_id, data.message_id, remember_style=data.remember_style)
    return {"job_id": str(job_id)}
