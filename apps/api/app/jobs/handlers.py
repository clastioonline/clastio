"""Job type -> handler registry. Imported by the worker (and by the API when jobs run inline)."""

from __future__ import annotations

import uuid
from typing import Any

from app.jobs.queue import JobContext, handler, on_failure
from app.services import courses, documents, sources, styles


@handler("assistant_reply", queue="ai")
async def assistant_reply(ctx: JobContext) -> dict[str, Any]:
    import time

    from sqlalchemy import update

    from app.core.db import get_sessionmaker
    from app.jobs.queue import PermanentJobError
    from app.models import GenerationJob, User
    from app.services import assistant

    await ctx.progress(10, "Thinking about your request")
    result = {"conversation_id": ctx.payload["conversation_id"], "text": "", "actions": []}
    last_saved = 0.0
    async with get_sessionmaker()() as db:
        user = await db.get(User, ctx.owner_id)
        if not user or user.status != "active":
            raise PermanentJobError("This account is no longer available.")
        async for ev in assistant.converse(db, user, ctx.payload["text"],
                                          uuid.UUID(ctx.payload["conversation_id"]), record_user=False):
            if ev["event"] == "token":
                result["text"] += ev["data"]["text"]
            elif ev["event"] == "action":
                result["actions"].append(ev["data"])
            if time.monotonic() - last_saved > 0.8 or ev["event"] == "done":
                async with get_sessionmaker()() as progress_db:
                    await progress_db.execute(update(GenerationJob).where(GenerationJob.id == ctx.job_id)
                                              .values(result=dict(result), stage="Preparing your reply", progress=50))
                    await progress_db.commit()
                last_saved = time.monotonic()
    return result


@handler("style_analysis", queue="docs")
async def style_analysis(ctx: JobContext) -> dict[str, Any]:
    await ctx.progress(5, "Analysing your slides")
    return await styles.process_style_upload(uuid.UUID(ctx.payload["file_id"]), name=ctx.payload.get("name"))


@on_failure("style_analysis")
async def style_analysis_failed(ctx: JobContext, error: str) -> None:
    from app.core.db import get_sessionmaker
    from app.models import UploadedFile

    async with get_sessionmaker()() as s:
        f = await s.get(UploadedFile, uuid.UUID(ctx.payload["file_id"]))
        if f:
            f.status, f.stage, f.error = "failed", "Failed", error[:1000]
            await s.commit()


@handler("source_indexing", queue="docs")
async def source_indexing(ctx: JobContext) -> dict[str, Any]:
    await ctx.progress(10, "Reading your document")
    return await sources.index_source(uuid.UUID(ctx.payload["file_id"]))


@on_failure("source_indexing")
async def source_indexing_failed(ctx: JobContext, error: str) -> None:
    await style_analysis_failed(ctx, error)


@handler("course_plan", queue="ai")
async def course_plan(ctx: JobContext) -> dict[str, Any]:
    return await courses.handle_course_plan(ctx)


@on_failure("course_plan")
async def course_plan_failed(ctx: JobContext, error: str) -> None:
    from app.core.db import get_sessionmaker
    from app.models import Course

    async with get_sessionmaker()() as s:
        c = await s.get(Course, uuid.UUID(ctx.payload["course_id"]))
        if c:
            c.status, c.error = "failed", error[:1000]
            await s.commit()


@handler("lesson_generation", queue="ai")
async def lesson_generation(ctx: JobContext) -> dict[str, Any]:
    return await courses.handle_lesson_generation(ctx)


on_failure("lesson_generation")(courses.on_lesson_failed)


@handler("slide_regeneration", queue="ai")
async def slide_regeneration(ctx: JobContext) -> dict[str, Any]:
    return await courses.handle_slide_regeneration(ctx)


@handler("lesson_render", queue="render")
async def lesson_render(ctx: JobContext) -> dict[str, Any]:
    return await courses.handle_lesson_render(ctx)


@handler("document_generation", queue="ai")
async def document_generation(ctx: JobContext) -> dict[str, Any]:
    return await documents.handle_document_generation(ctx)


on_failure("document_generation")(documents.on_document_failed)


@handler("media_generation", queue="ai")
async def media_generation(ctx: JobContext) -> dict[str, Any]:
    from app.services import media

    return await media.handle_media_generation(ctx)


@on_failure("media_generation")
async def media_generation_failed(ctx: JobContext, error: str) -> None:
    from app.services import media

    await media.handle_media_failed(ctx, error)


@handler("template_preview", queue="docs")
async def template_preview(ctx: JobContext) -> dict[str, Any]:
    from app.core.db import get_sessionmaker
    from app.core.storage import get_storage
    from app.jobs.queue import PermanentJobError
    from app.models import Template

    await ctx.progress(10, "Refreshing template previews")
    async with get_sessionmaker()() as db:
        template = await db.get(Template, uuid.UUID(ctx.payload["template_id"]))
        if not template or template.owner_id != ctx.owner_id:
            raise PermanentJobError("Template is no longer available")
        base = await get_storage().get(template.base_storage_key)
        previews = await styles.render_previews(template.id, base, template.spec)
        if not previews:
            raise PermanentJobError("Preview rendering failed. Your saved design is preserved.")
        template.preview_keys = previews
        await db.commit()
    return {"template_id": ctx.payload["template_id"]}


@handler("image_replacement", queue="ai")
async def image_replacement(ctx: JobContext) -> dict[str, Any]:
    from app.services.image_assistant import replace
    return await replace(ctx)


@handler("whatsapp_voice", queue="ai")
async def whatsapp_voice(ctx: JobContext) -> dict[str, Any]:
    from app.services.voice import handle

    return await handle(ctx)


@handler("admin_push_campaign", queue="default")
async def admin_push_campaign(ctx: JobContext) -> dict[str, Any]:
    from app.services.push_campaigns import handle_campaign

    return await handle_campaign(ctx)


@handler("book_import", queue="docs")
async def book_import(ctx: JobContext) -> dict[str, Any]:
    from app.core.config import get_settings
    from app.core.db import get_sessionmaker
    from app.jobs.queue import PermanentJobError
    from app.models import User
    from app.services.book_library import import_pdf

    await ctx.progress(10, "Saving the book PDF")
    async with get_sessionmaker()() as db:
        user = await db.get(User, ctx.owner_id)
        if not user or user.status != "active":
            raise PermanentJobError("This account is no longer available.")
        from app.api.routes.content import upload_limit_mb
        cap = min(get_settings().max_upload_mb, await upload_limit_mb(db, user))*1024*1024
        body = ctx.payload
        book, _ = await import_pdf(db, user, url=body['url'], title=body['title'],
            metadata={key:body[key] for key in ['grade','subject','curriculum','edition','language']},
            rights_confirmed=body['rights_confirmed'], max_bytes=cap)
        return {'file_id':str(book.id), 'filename':book.filename}


@handler('book_catalogue_copy', queue='docs')
async def book_catalogue_copy(ctx: JobContext) -> dict[str, Any]:
    from app.api.routes.content import upload_limit_mb
    from app.core.db import get_sessionmaker
    from app.jobs.queue import PermanentJobError
    from app.models import User
    from app.services.book_catalog import copy_to_library

    await ctx.progress(10, 'Adding a saved catalogue book')
    async with get_sessionmaker()() as db:
        user = await db.get(User, ctx.owner_id)
        if not user or user.status != 'active':
            raise PermanentJobError('This account is no longer available.')
        book = await copy_to_library(db, user, uuid.UUID(ctx.payload['file_id']),
                                     await upload_limit_mb(db, user)*1024*1024)
        return {'file_id': str(book.id), 'filename': book.filename}
