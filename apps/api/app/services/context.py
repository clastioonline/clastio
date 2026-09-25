"""Build the TEACHING CONTEXT block that personalises every generation.

Order matters for prompt caching: stable facts (profile, preferences) first, volatile facts
(recent lessons, retrieved sources) last. No student personal data is ever included.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClassSection, TeacherProfile, User
from app.services import memory as memory_svc
from app.services import sources as source_svc

CURRICULUM_NAMES = {
    "british": "British (England National Curriculum / Cambridge & Edexcel IGCSE)",
    "cbse": "Indian CBSE (NCERT)", "icse": "Indian ICSE", "american": "American (Common Core / NGSS)",
    "ib": "International Baccalaureate (PYP/MYP/DP)", "moe": "UAE Ministry of Education",
    "uae_ai": "UAE Ministry of Education AI Curriculum", "other": "Other",
}
COUNTRY_NOTES = {
    "AE": "Students are in the UAE: many are EAL learners; use local, culturally appropriate examples "
          "(e.g. desalination, date palms, Expo City, UAE wildlife) where they genuinely help.",
    "IN": "Students are in India: use Indian contexts and examples where they genuinely help; align to NCERT wording "
          "for CBSE.",
}


def _fmt_pref(key: str, value: Any) -> str:
    label = memory_svc.PREFERENCE_LABELS.get(key, key.replace("_", " ").capitalize())
    if isinstance(value, bool):
        value = "yes" if value else "no"
    elif isinstance(value, list):
        value = ", ".join(str(v) for v in value)
    return f"{label}: {value}"


async def build_context(db: AsyncSession, user: User, *, topic: str | None = None,
                        class_section_id: uuid.UUID | None = None, subject: str | None = None,
                        include_sources: bool = True) -> tuple[str, dict[str, Any]]:
    """Returns (context_text, context_meta)."""
    lines: list[str] = []
    meta: dict[str, Any] = {}
    tp = (await db.execute(select(TeacherProfile).where(TeacherProfile.user_id == user.id))).scalars().first()
    if tp:
        lines.append(f"Teacher: {user.name or 'the teacher'} — {CURRICULUM_NAMES.get(tp.curriculum, tp.curriculum)} "
                     f"curriculum, {tp.country}{', ' + tp.region if tp.region else ''}"
                     f"{', ' + tp.school_name if tp.school_name else ''}.")
        lines.append(f"Subjects: {', '.join(tp.subjects) or 'n/a'}. Grades: {', '.join(tp.grades) or 'n/a'}. "
                     f"Teaching language(s): {', '.join(tp.teaching_languages)}. Typical lesson: "
                     f"{tp.class_duration_minutes} min.")
        if tp.teaching_style:
            lines.append(f"Teaching style (teacher's words): {tp.teaching_style}")
        if note := COUNTRY_NOTES.get(tp.country):
            lines.append(note)
        meta["country"] = tp.country
    prefs = await memory_svc.list_preferences(db, user.id)
    stated = [_fmt_pref(p.key, p.value) for p in prefs if p.confirmed]
    inferred = [_fmt_pref(p.key, p.value) for p in prefs if not p.confirmed]
    if stated:
        lines.append("Teacher preferences (apply these): " + "; ".join(stated) + ".")
    if inferred:
        lines.append("Observed from the teacher's own slides (follow unless it conflicts): " + "; ".join(inferred) + ".")
    meta["preferences"] = {p.key: p.value for p in prefs}

    if class_section_id:
        cs = await db.get(ClassSection, class_section_id)
        if cs and cs.user_id == user.id:
            lines.append(f"Class {cs.name} (Grade {cs.grade} {cs.subject}): pace {cs.pace}, ability mix {cs.ability_mix}, "
                         f"about {cs.eal_percent}% EAL learners."
                         + (f" Support needs (aggregate): {cs.send_notes}." if cs.send_notes else "")
                         + (f" Notes: {cs.notes}." if cs.notes else ""))
            recent = await memory_svc.recent_memory(db, user.id, class_section_id=cs.id,
                                                    kinds=["lesson_summary", "reflection", "misconception"], limit=6)
            if recent:
                lines.append("Recent history with this class:\n" + "\n".join(f"- {m.content}" for m in recent))
    if topic:
        related = await memory_svc.search_memory(db, user.id, f"{subject or ''} {topic}", k=4,
                                                 kinds=["misconception", "feedback", "note", "reflection"])
        if related:
            lines.append("Relevant notes from teacher memory:\n" + "\n".join(f"- {m.content}" for m in related))
        if include_sources:
            chunks = await source_svc.retrieve(db, user.id, f"{subject or ''} {topic}", k=5)
            if chunks:
                meta["sources"] = [{"file": c["file"], "page": c["page"], "file_id": c["file_id"]} for c in chunks]
                lines.append("Reference material from the teacher's uploaded sources (prefer these facts and wording):\n"
                             + "\n".join(f"[{c['file']} p.{c['page']}] {c['text'][:700]}" for c in chunks))
    text = "\n".join(lines)
    return text[:12000], meta
