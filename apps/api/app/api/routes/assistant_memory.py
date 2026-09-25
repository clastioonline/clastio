from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sse_starlette.sse import EventSourceResponse

from app.core.deps import DB, CurrentUser
from app.core.errors import NotFound
from app.core.ratelimit import rate_limit
from app.models import Conversation, ConversationMessage, TeacherMemory, TeacherPreference
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
    row = await memory_svc.set_preference(db, user.id, key[:80], data.value, source="stated")
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


@router.post("/assistant/messages", dependencies=[Depends(rate_limit("assistant", 40, 600))])
async def message(data: MessageIn, user: CurrentUser, db: DB):
    async def gen():
        async for ev in assistant.converse(db, user, data.text, data.conversation_id):
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
    return {"id": str(c.id), "title": c.title,
            "messages": [{"role": m.role, "content": m.content, "actions": m.actions,
                          "created_at": m.created_at.isoformat()} for m in msgs]}
