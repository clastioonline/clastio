"""Job type -> handler registry. Imported by the worker (and by the API when jobs run inline)."""

from __future__ import annotations

import uuid
from typing import Any

from app.jobs.queue import JobContext, handler, on_failure
from app.services import courses, documents, sources, styles


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
