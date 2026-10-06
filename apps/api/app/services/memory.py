"""Teacher memory: structured preferences, episodic memory (with embeddings) and learned signals."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import get_ai
from app.models import TeacherMemory, TeacherPreference

PREFERENCE_LABELS: dict[str, str] = {
    "preferred_image_style": "Preferred image style",
    "preferred_image_source": "Preferred image source",
    "language_level": "Language level",
    "explanation_depth": "Explanation depth",
    "tone": "Tone",
    "preferred_layouts": "Preferred slide layouts",
    "slides_per_lesson": "Slides per lesson",
    "bullets_per_slide": "Bullets per slide",
    "words_per_bullet": "Words per bullet",
    "quiz_length": "Quiz length",
    "recap_first": "Start with a recap",
    "homework_last": "End with homework",
    "real_world_examples": "Real-world examples",
    "visual_explanations": "Visual explanations",
    "preferred_activities": "Preferred activities",
    "assessment_style": "Assessment style",
    "uses_question_titles": "Question-style titles",
    "uses_images": "Uses images",
    "bilingual_vocabulary": "Bilingual vocabulary slides",
    "local_context": "Local (UAE/India) context",
    "ai_disclosure": "Add AI-use note to files",
}


async def get_preferences(db: AsyncSession, user_id: uuid.UUID, *, confirmed_only: bool = False) -> dict[str, Any]:
    rows = (await db.execute(select(TeacherPreference).where(TeacherPreference.user_id == user_id))).scalars().all()
    return {r.key: r.value for r in rows if r.confirmed or not confirmed_only}


async def list_preferences(db: AsyncSession, user_id: uuid.UUID) -> list[TeacherPreference]:
    return list((await db.execute(select(TeacherPreference).where(TeacherPreference.user_id == user_id)
                                  .order_by(TeacherPreference.key))).scalars().all())


async def set_preference(db: AsyncSession, user_id: uuid.UUID, key: str, value: Any, *, source: str = "stated",
                         confidence: float = 1.0) -> TeacherPreference:
    row = (await db.execute(select(TeacherPreference).where(TeacherPreference.user_id == user_id,
                                                              TeacherPreference.key == key))).scalars().first()
    if row is None:
        row = TeacherPreference(user_id=user_id, key=key)
        db.add(row)
    elif row.source == "stated" and source == "inferred":
        return row  # never overwrite what the teacher told us with a guess
    row.value, row.source, row.confidence = value, source, confidence
    row.confirmed = source == "stated"
    await db.flush()
    return row


async def add_memory(db: AsyncSession, user_id: uuid.UUID, kind: str, content: str, *, meta: dict | None = None,
                     class_section_id: uuid.UUID | None = None, lesson_id: uuid.UUID | None = None,
                     embed: bool = True) -> TeacherMemory:
    vec = None
    if embed:
        try:
            vec = (await get_ai().embed([content], owner_id=user_id))[0]
        except Exception:
            vec = None
    m = TeacherMemory(user_id=user_id, kind=kind, content=content[:4000], meta=meta or {},
                      class_section_id=class_section_id, lesson_id=lesson_id, embedding=vec)
    db.add(m)
    await db.flush()
    return m


async def search_memory(db: AsyncSession, user_id: uuid.UUID, query: str, k: int = 5,
                        kinds: list[str] | None = None) -> list[TeacherMemory]:
    try:
        vec = (await get_ai().embed([query], owner_id=user_id))[0]
    except Exception:
        return await lexical_memory(db, user_id, query, k=k, kinds=kinds)
    q = select(TeacherMemory).where(TeacherMemory.user_id == user_id, TeacherMemory.embedding.is_not(None))
    if kinds:
        q = q.where(TeacherMemory.kind.in_(kinds))
    q = q.order_by(TeacherMemory.embedding.cosine_distance(vec)).limit(k)
    rows = list((await db.execute(q)).scalars().all())
    return rows or await lexical_memory(db, user_id, query, k=k, kinds=kinds)


async def recent_memory(db: AsyncSession, user_id: uuid.UUID, *, kinds: list[str] | None = None,
                        class_section_id: uuid.UUID | None = None, limit: int = 8) -> list[TeacherMemory]:
    q = select(TeacherMemory).where(TeacherMemory.user_id == user_id)
    if kinds:
        q = q.where(TeacherMemory.kind.in_(kinds))
    if class_section_id:
        q = q.where(TeacherMemory.class_section_id == class_section_id)
    q = q.order_by(TeacherMemory.created_at.desc()).limit(limit)
    return list((await db.execute(q)).scalars().all())


async def learn_from_slide_edit(db: AsyncSession, user_id: uuid.UUID, before: dict, after: dict) -> None:
    """If the teacher keeps shortening bullets, lower the inferred words-per-bullet preference."""
    def avg_words(slide: dict) -> float | None:
        bl = [b.get("text", "") for b in slide.get("bullets", [])]
        return sum(len(t.split()) for t in bl) / len(bl) if bl else None

    b, a = avg_words(before), avg_words(after)
    if b is None or a is None or b == 0:
        return
    ratio = a / b
    if 0.3 < ratio < 0.85:
        prefs = await get_preferences(db, user_id)
        current = prefs.get("words_per_bullet") or b
        try:
            new = round(max(4.0, float(current) * 0.9), 1)
        except (TypeError, ValueError):
            new = round(a, 1)
        await set_preference(db, user_id, "words_per_bullet", new, source="inferred", confidence=0.8)


async def lexical_memory(db: AsyncSession, user_id: uuid.UUID, query: str, *, k: int = 5,
                         kinds: list[str] | None = None) -> list[TeacherMemory]:
    """Owner-scoped fallback when embeddings are unavailable, bounded to 60 recent notes."""
    from app.services.teacher_signals import memory_terms
    terms = memory_terms(query)
    if not terms:
        return []
    rows = await recent_memory(db, user_id, kinds=kinds, limit=60)
    scored = [(len(terms & memory_terms(row.content)), row) for row in rows]
    return [row for score, row in sorted(scored, key=lambda item: item[0], reverse=True) if score][:k]
