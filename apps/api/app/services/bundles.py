"""Complete bundle orchestration under one queued job and completion notification."""
from __future__ import annotations

import uuid

from sqlalchemy.dialects.postgresql import insert

from app.core.db import get_sessionmaker, utcnow
from app.jobs.queue import JobContext
from app.models import Document, Lesson
from app.services.documents import handle_document_generation


async def complete_bundle(ctx: JobContext, lesson_id: uuid.UUID, owner_id: uuid.UUID) -> list[str]:
    ids = []
    for kind in ("lesson_plan", "worksheet", "quiz"):
        # Stable IDs make retries reuse documents rather than multiplying deliverables.
        document_id = uuid.uuid5(ctx.job_id, kind)
        async with get_sessionmaker()() as db:
            lesson = await db.get(Lesson, lesson_id)
            await db.execute(insert(Document).values(
                id=document_id, owner_id=owner_id, lesson_id=lesson_id, course_id=lesson.course_id,
                kind=kind, title=f"{kind.replace('_', ' ').title()} · {lesson.title}",
                difficulty="tiered" if kind == "worksheet" else "mixed", status="queued",
                files={}, content={"options": {"num_questions": 9 if kind == "worksheet" else 6,
                                              "instructions": "Use Support, Core and Extension sections with questions at each tier." if kind == "worksheet" else ""}},
                created_at=utcnow(), updated_at=utcnow()).on_conflict_do_nothing(index_elements=["id"]))
            doc = await db.get(Document, document_id)
            ready = doc.status == "ready"
            await db.commit()
        if not ready:
            child = JobContext(job_id=ctx.job_id, owner_id=owner_id, payload={"document_id": str(document_id)})
            await handle_document_generation(child)
        ids.append(str(document_id))
    return ids
