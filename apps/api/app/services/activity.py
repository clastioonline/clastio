"""Owner-scoped activity summaries, without exposing job payloads or provider internals."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Conversation,
    Course,
    Document,
    GenerationJob,
    Lesson,
    MediaItem,
    Template,
    UploadedFile,
)

LABELS = {
    "style_analysis": "Learn your presentation style", "source_indexing": "Read reference material", "book_import": "Save book PDF", "book_catalogue_copy": "Add catalogue book",
    "course_plan": "Plan your lessons", "lesson_generation": "Build lesson slides",
    "slide_regeneration": "Update a slide", "lesson_render": "Rebuild presentation",
    "document_generation": "Create a worksheet or quiz", "media_generation": "Create lesson media",
    "image_replacement": "Replace lesson image", "assistant_reply": "Assistant reply", "template_preview": "Refresh template previews",
}


async def summaries(db: AsyncSession, jobs: list[GenerationJob]) -> list[dict]:
    objects = {}
    for field, model in (("course_id", Course), ("lesson_id", Lesson), ("document_id", Document),
                         ("template_id", Template), ("media_id", MediaItem), ("file_id", UploadedFile), ("conversation_id", Conversation)):
        ids = {uuid.UUID(j.payload[field]) for j in jobs if j.payload.get(field)}
        if ids:
            objects[field] = {str(x.id): x for x in (await db.execute(select(model).where(model.id.in_(ids)))).scalars()}
    out = []
    for j in jobs:
        title, href = LABELS.get(j.type, "Background task"), "/activity"
        if j.type in {"book_import", "book_catalogue_copy"}:
            title, href = j.payload.get("title") or title, "/books"
        for field, group in objects.items():
            obj = group.get(j.payload.get(field))
            if not obj or obj.owner_id != j.owner_id:
                continue
            if field == "course_id":
                title, href = obj.topic, f"/projects/{obj.project_id}"
            elif field == "lesson_id":
                title, href = obj.title, f"/lessons/{obj.id}"
            elif field == "document_id":
                title, href = obj.title, f"/lessons?tab=documents&document={obj.id}"
            elif field == "template_id":
                title, href = obj.name, f"/templates/{obj.id}"
            elif field == "media_id":
                title, href = obj.prompt[:100], "/media"
            elif field == "file_id":
                title = j.payload.get("name") or title
                tid = (j.result or {}).get("template_id")
                href = f"/templates/{tid}" if tid else "/templates" if j.type == "style_analysis" else "/projects/new"
            elif field == "conversation_id":
                title, href = obj.title, f"/assistant?conversation={obj.id}"
        out.append({"id": str(j.id), "type": j.type, "label": LABELS.get(j.type, "Background task"),
                    "title": title, "href": href, "status": j.status, "progress": j.progress,
                    "stage": j.stage, "created_at": j.created_at.isoformat(),
                    "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                    "error": "This task couldn't finish. Open it to review or try again." if j.status == "failed" else None})
    return out
