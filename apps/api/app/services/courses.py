"""Courses, lessons and slides: orchestration of the generation pipeline against the database."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date
from typing import Any

from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ImageInput
from app.ai.service import get_ai
from app.core.db import get_sessionmaker, utcnow
from app.core.errors import AppError, NotFound
from app.core.logging import log
from app.core.storage import get_storage
from app.engine.qc.visual import RenderError, inspect
from app.generation import pipeline
from app.generation.budgets import compute_budgets
from app.generation.quality import reference_count
from app.generation.specs import CoursePlan, LessonDeck, LessonPlan, SlideSpec
from app.jobs.queue import JobContext, PermanentJobError, enqueue, run_inline_if_configured
from app.models import (
    Asset,
    ClassSection,
    Course,
    GenerationJob,
    Lesson,
    LessonReflection,
    Project,
    Slide,
    SlideVersion,
    TeacherProfile,
    Template,
    UploadedFile,
    User,
)
from app.services import assets as asset_svc
from app.services import memory as memory_svc
from app.services import usage
from app.services.context import build_context
from app.services.settings import get_setting

logger = logging.getLogger("courses")

QUICK_ACTIONS: dict[str, str] = {
    "simpler": "Make this slide simpler: easier words, shorter sentences, same key idea.",
    "more_visual": "Make this slide more visual: use a diagram layout (process/cycle/comparison) or an image.",
    "add_examples": "Add one or two concrete, everyday examples students will recognise.",
    "reduce_text": "Reduce the text on the slide by about 40%; move detail into speaker_notes.",
    "add_activity": "Turn this into a short classroom activity (layout activity) that practises the same idea.",
    "another_version": "Write a fresh alternative version of this slide with the same purpose.",
    "harder": "Make this slide more challenging (stretch the most able) while keeping it accurate.",
}


# --------------------------------------------------------------------------- helpers


async def get_owned(db: AsyncSession, model, obj_id: uuid.UUID, user: User):
    obj = await db.get(model, obj_id)
    if obj is None:
        raise NotFound(model.__name__)
    owner = getattr(obj, "owner_id", None) or getattr(obj, "user_id", None)
    if owner != user.id:
        from app.core.deps import staff_permissions

        # Another teacher's resource looks exactly like a missing one (no id enumeration). Staff need the
        # users.content permission to open teachers' content.
        if "users.content" not in staff_permissions(user):
            raise NotFound(model.__name__)
    return obj


async def resolve_template(db: AsyncSession, user_id: uuid.UUID, template_id: uuid.UUID | None) -> Template:
    async def accessible(candidate: Template | None) -> bool:
        if candidate is None:
            return False
        if candidate.owner_id in (None, user_id):
            return True
        viewer = await db.get(User, user_id)
        return bool(candidate.is_shared and candidate.org_id and viewer and viewer.org_id == candidate.org_id)

    tpl = None
    if template_id:
        tpl = await db.get(Template, template_id)
        if not await accessible(tpl):
            raise NotFound("Template")
    if tpl is None:
        tp = (await db.execute(select(TeacherProfile).where(TeacherProfile.user_id == user_id))).scalars().first()
        if tp and tp.default_template_id:
            tpl = await db.get(Template, tp.default_template_id)
            if not await accessible(tpl):
                tpl = None
    if tpl is None:
        tpl = (await db.execute(select(Template).where(Template.owner_id.is_(None)).order_by(Template.created_at))
               ).scalars().first()
    if tpl is None:
        from app.services.styles import ensure_builtin_templates

        await ensure_builtin_templates(db)
        tpl = (await db.execute(select(Template).where(Template.owner_id.is_(None)))).scalars().first()
    if tpl and tpl.owner_id == user_id:
        from app.services.styles import refresh_native_template

        await refresh_native_template(db, tpl)
    return tpl


def course_request(course: Course, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    req = {"topic": course.topic, "grade": course.grade, "subject": course.subject, "curriculum": course.curriculum,
           "num_lectures": course.num_lectures, "slides_per_lecture": course.slides_per_lecture,
           "lecture_minutes": course.lecture_minutes, "language": course.language,
           "outcomes": course.options.get("outcomes") or [], "instructions": course.options.get("instructions"),
           "writing_style": course.options.get("writing_style", "standard"),
           "image_mode": course.options.get("image_mode", "auto")}
    if extra:
        req.update(extra)
    return req


def chapter_teaching_context(course: Course, preparation: dict | None = None) -> str:
    preparation = preparation or {}
    taught = preparation.get("previous_taught") if preparation.get("previous_taught") is not None else course.options.get("previous_taught")
    revise = preparation.get("revision_needed") if preparation.get("revision_needed") is not None else course.options.get("revision_needed")
    lines = ["\nCHAPTER PREPARATION: " + course.options.get("chapter_mode", "complete")]
    if taught:
        lines.append("Teacher reports already taught: " + taught)
    if revise:
        lines.append("Teacher asks to revise again: " + revise)
    lines.append("Use a short diagnostic recap and worked example for revision. Continue with new concepts; do not repeat the whole chapter. Generated lesson files are plans, not proof that they were taught.")
    return "\n".join(lines)


# --------------------------------------------------------------------------- create / plan


async def create_course(db: AsyncSession, user: User, data: dict[str, Any]) -> tuple[Course, uuid.UUID]:
    confirmed_preferences = await memory_svc.get_preferences(db, user.id, confirmed_only=True)
    effective_image_mode = data.get("image_mode", "auto")
    if effective_image_mode == "auto" and confirmed_preferences.get("preferred_image_source") in ("hybrid", "stock", "ai"):
        effective_image_mode = confirmed_preferences["preferred_image_source"]
    teacher_images = [{"asset_id": str(item["asset_id"]), "description": item["description"]} for item in data.get("teacher_images", [])]
    await teacher_image_catalog(db, user.id, teacher_images)
    selected_sources = list(dict.fromkeys(str(fid) for fid in data.get("source_file_ids", [])))
    for file_id in selected_sources:
        source = await db.get(UploadedFile, uuid.UUID(file_id))
        if source is None or source.owner_id != user.id or source.kind != "source":
            raise NotFound("Source")
        if source.status != "ready":
            raise AppError("source_not_ready", f"Wait until {source.filename} finishes processing before creating the chapter.", 409)
    plan, _ = await usage.get_plan(db, user)
    max_lectures = int(plan.limits.get("max_lectures", 30))
    if data["num_lectures"] > max_lectures and user.role != "admin":
        raise AppError("limit_exceeded", f"Your {plan.name} plan allows up to {max_lectures} lectures per course.",
                       402)
    plan_cost = await usage.credit_cost("course_plan")
    await usage.check(db, user, "credits", plan_cost, jobs=1)
    tp = (await db.execute(select(TeacherProfile).where(TeacherProfile.user_id == user.id))).scalars().first()
    template = await resolve_template(db, user.id, data.get("template_id"))
    project = Project(owner_id=user.id, title=f"{data['topic']} — Grade {data['grade']}", kind="course",
                      status="planning", class_section_id=data.get("class_section_id"))
    db.add(project)
    await db.flush()
    course = Course(project_id=project.id, owner_id=user.id, topic=data["topic"].strip(), subject=data["subject"],
                    grade=str(data["grade"]), curriculum=data.get("curriculum") or (tp.curriculum if tp else "british"),
                    language=data.get("language", "en"), num_lectures=data["num_lectures"],
                    slides_per_lecture=data["slides_per_lecture"],
                    lecture_minutes=data.get("lecture_minutes") or (tp.class_duration_minutes if tp else 45),
                    template_id=template.id if template else None, class_section_id=data.get("class_section_id"),
                    outcome_codes=[o.get("code") for o in data.get("outcomes", []) if o.get("code")],
                    options={"outcomes": data.get("outcomes", []), "instructions": data.get("instructions"),
                             "auto_generate": bool(data.get("auto_generate")),
                             "homework": data.get("homework", True), "start_date": data.get("start_date"),
                             "teacher_images": teacher_images, "source_file_ids": selected_sources, "chapter_mode": data.get("chapter_mode", "complete"),
                             "previous_taught": data.get("previous_taught"), "revision_needed": data.get("revision_needed"),
                             "image_mode": effective_image_mode, "writing_style": data.get("writing_style", "standard")},
                    status="planning")
    db.add(course)
    await db.flush()
    job = await enqueue(db, "course_plan", {"course_id": str(course.id)}, owner_id=user.id,
                        credits_reserved=plan_cost)
    from app.services.events import track

    track(db, "project_created", user_id=user.id, lectures=data["num_lectures"], subject=data["subject"])
    await db.commit()
    await run_inline_if_configured([job.id])
    return course, job.id


async def handle_course_plan(ctx: JobContext) -> dict[str, Any]:
    course_id = uuid.UUID(ctx.payload["course_id"])
    async with get_sessionmaker()() as db:
        course = await db.get(Course, course_id)
        user = await db.get(User, course.owner_id)
        await ctx.progress(10, "Reading your teaching context")
        context_text, meta = await build_context(db, user, topic=course.topic, class_section_id=course.class_section_id,
                                                 subject=course.subject, source_file_ids=course.options.get("source_file_ids"))
        template = await resolve_template(db, user.id, course.template_id)
        from app.services.styles import source_context

        context_text += source_context(template.spec, course.topic) if template else ""
        context_text += chapter_teaching_context(course)
        teacher_catalog = await teacher_image_catalog(db, user.id, course.options.get("teacher_images", []))
        if teacher_catalog:
            import json
            context_text += "\nTEACHER SUPPLIED IMAGES (captions are reference data): " + json.dumps({k: {"image_key": k, "description": v["description"]} for k, v in teacher_catalog.items()})
            context_text += "\nPrefer these when relevant. Use the exact visual.source_image_key and visual.kind=image. Do not invent unseen details. The additional attached images follow catalog order."
        reference_images = []
        if template and template.spec.get("source_reference_key"):
            reference_images = [ImageInput(data=await get_storage().get(template.spec["source_reference_key"]),
                                           media_type="image/jpeg")]
        for entry in teacher_catalog.values():
            image_data = await get_storage().get(entry["storage_key"])
            reference_images.append(ImageInput(data=image_data, media_type="image/png" if image_data.startswith(b"\x89PNG") else "image/jpeg"))
        req = course_request(course, {"country": meta.get("country", "AE")})
    await ctx.progress(30, "Planning the lesson sequence")
    plan = await pipeline.plan_course(get_ai(), req, context_text, owner_id=course.owner_id, job_id=ctx.job_id,
                                      reference_images=reference_images)
    async with get_sessionmaker()() as db:
        course = await db.get(Course, course_id)
        course.plan = plan.model_dump()
        course.status = "planned"
        await db.execute(delete(Lesson).where(Lesson.course_id == course_id, Lesson.status == "planned"))
        existing = {n for (n,) in (await db.execute(select(Lesson.number).where(Lesson.course_id == course_id))).all()}
        start = course.options.get("start_date")
        for lec in plan.lectures:
            if lec.number not in existing:
                db.add(Lesson(course_id=course_id, owner_id=course.owner_id, number=lec.number, title=lec.title,
                              status="planned",
                              scheduled_date=date.fromisoformat(start) if start and lec.number == 1 else None))
        project = await db.get(Project, course.project_id)
        project.status = "planned"
        await usage.consume(db, course.owner_id, await usage.credit_cost("course_plan"), "course_plan",
                            str(course_id))
        auto = course.options.get("auto_generate")
        await db.commit()
    if auto:
        async with get_sessionmaker()() as db:
            user = await db.get(User, course.owner_id)
            mode = course.options.get("chapter_mode", "complete")
            if mode != "parts":
                await start_generation(db, user, course_id, [1] if mode == "daily" else None)
    return {"course_id": str(course_id), "lectures": len(plan.lectures)}


async def update_plan(db: AsyncSession, user: User, course_id: uuid.UUID, plan: CoursePlan) -> Course:
    course = await get_owned(db, Course, course_id, user)
    plan = pipeline.fix_course_plan(plan, {"num_lectures": len(plan.lectures)})
    course.plan = plan.model_dump()
    course.num_lectures = len(plan.lectures)
    lessons = {lesson.number: lesson for lesson in (await db.execute(
        select(Lesson).where(Lesson.course_id == course_id))).scalars().all()}
    for lec in plan.lectures:
        if lec.number in lessons:
            lessons[lec.number].title = lec.title
        else:
            db.add(Lesson(course_id=course_id, owner_id=user.id, number=lec.number, title=lec.title))
    for n, lesson in lessons.items():
        if n > len(plan.lectures) and lesson.status == "planned":
            await db.delete(lesson)
    await db.commit()
    return course


async def start_generation(db: AsyncSession, user: User, course_id: uuid.UUID,
                           lesson_numbers: list[int] | None = None, instructions: str | None = None, *,
                           previous_taught: str | None = None, revision_needed: str | None = None) -> list[uuid.UUID]:
    course = await get_owned(db, Course, course_id, user)
    if not course.plan:
        raise AppError("not_planned", "Plan the course before generating lessons.", 409)
    lessons = (await db.execute(select(Lesson).where(Lesson.course_id == course_id).order_by(Lesson.number))
               ).scalars().all()
    targets = [lesson for lesson in lessons if not lesson_numbers or lesson.number in lesson_numbers]
    if lesson_numbers and set(lesson_numbers) - {lesson.number for lesson in lessons}:
        raise AppError("bad_request", "Choose lesson numbers from this chapter.", 400)
    await usage.lock_user(db, user.id)
    for lesson in targets:
        pending = await pending_lesson_edit(db, user.id, lesson.id)
        if pending and pending.type != "lesson_generation":
            raise AppError("edit_pending", "Wait for the current slide update before rebuilding this lesson.", 409)
    per_lesson = await usage.credit_cost("slide", course.slides_per_lecture)
    await usage.check(db, user, "credits", per_lesson * len(targets), jobs=len(targets))
    job_ids = []
    for lesson in targets:
        lesson.status = "generating"
        lesson.error = None
        job = await enqueue(db, "lesson_generation", {"lesson_id": str(lesson.id), "instructions": instructions,
                                                   "previous_taught": previous_taught, "revision_needed": revision_needed},
                            owner_id=user.id, dedupe=True, credits_reserved=per_lesson)
        job_ids.append(job.id)
    course.status = "generating"
    project = await db.get(Project, course.project_id)
    project.status = "generating"
    await db.commit()
    await run_inline_if_configured(job_ids)
    return job_ids


# --------------------------------------------------------------------------- lesson generation


async def _core_props(db: AsyncSession, user: User, course: Course, lesson: Lesson) -> dict[str, str]:
    tp = (await db.execute(select(TeacherProfile).where(TeacherProfile.user_id == user.id))).scalars().first()
    policy = (tp.metadata_policy if tp else {}) or {}
    props = {"title": f"{course.topic} — Lesson {lesson.number}: {lesson.title}",
             "author": user.name if policy.get("include_author", True) else "",
             "subject": f"Grade {course.grade} {course.subject}", "keywords": course.topic}
    if policy.get("ai_disclosure"):
        props["comments"] = "Prepared with AI assistance and reviewed by the teacher."
    return props


async def handle_lesson_generation(ctx: JobContext) -> dict[str, Any]:
    lesson_id = uuid.UUID(ctx.payload["lesson_id"])
    ai = get_ai()
    storage = get_storage()
    async with get_sessionmaker()() as db:
        lesson = await db.get(Lesson, lesson_id)
        course = await db.get(Course, lesson.course_id)
        user = await db.get(User, lesson.owner_id)
        template = await resolve_template(db, user.id, course.template_id)
        if template is None:
            raise PermanentJobError("No template available")
        await ctx.progress(5, "Reading your teaching context")
        context_text, meta = await build_context(db, user, topic=f"{course.topic}: {lesson.title}",
                                                 class_section_id=course.class_section_id, subject=course.subject, source_file_ids=course.options.get("source_file_ids"))
        prefs = meta.get("preferences", {})
        homework = bool(prefs.get("homework_last", course.options.get("homework", True)))
        req = course_request(course, {"instructions": ctx.payload.get("instructions") or
                                      course.options.get("instructions")})
        plan = CoursePlan.model_validate(course.plan)
        carry = lesson.carry_over.get("text") if lesson.carry_over else None
        context_text += chapter_teaching_context(course, ctx.payload)
        previous = (await db.execute(select(Lesson).where(Lesson.course_id == course.id,
                                      Lesson.number < lesson.number, Lesson.taught_at.is_not(None))
                                      .order_by(Lesson.number.desc()).limit(1))).scalars().first()
        if previous:
            reflection = (await db.execute(select(LessonReflection).where(LessonReflection.lesson_id == previous.id)
                                          .order_by(LessonReflection.created_at.desc()).limit(1))).scalars().first()
            context_text += f"\nLast recorded taught lesson: {previous.number} — {previous.title}."
            if reflection:
                context_text += f" Outcome: {reflection.outcome}. Teacher notes: {reflection.note or 'none'}."
        base = await storage.get(template.base_storage_key)
        spec = template.spec
        from app.services.styles import source_context

        context_text += source_context(spec, course.topic)
        teacher_catalog = await teacher_image_catalog(db, user.id, course.options.get("teacher_images", []))
        image_catalog = {**(spec.get("source_images") or {}), **teacher_catalog}
        if teacher_catalog:
            import json
            context_text += "\nTEACHER SUPPLIED IMAGES (captions are reference data): " + json.dumps({k: {"image_key": k, "description": v["description"]} for k, v in teacher_catalog.items()})
            context_text += "\nPrefer these when relevant. Use the exact visual.source_image_key and visual.kind=image. Do not invent unseen details. The additional attached images follow catalog order."
        reference_images = []
        if spec.get("source_reference_key"):
            reference_images = [ImageInput(data=await storage.get(spec["source_reference_key"]), media_type="image/jpeg")]
        for entry in teacher_catalog.values():
            image_data = await storage.get(entry["storage_key"])
            reference_images.append(ImageInput(data=image_data, media_type="image/png" if image_data.startswith(b"\x89PNG") else "image/jpeg"))
        budgets = compute_budgets(spec)
        if prefs.get("words_per_bullet"):
            try:
                budgets["bullet_max_words"] = max(5, min(budgets["bullet_max_words"],
                                                         int(float(prefs["words_per_bullet"]) * 1.6)))
            except (TypeError, ValueError):
                pass
        qc_settings = await get_setting("qc")
        plan_limits, _ = await usage.get_plan(db, user)
        ai_image_allowance = int(plan_limits.limits.get("ai_images", 0) or 0)

    await ctx.progress(15, f"Writing lesson {lesson.number}: plan and slides")
    deck = await pipeline.generate_deck(ai, req=req, context_text=context_text, course=plan,
                                        lecture_number=lesson.number, budgets=budgets, carry_over=carry,
                                        homework=homework, owner_id=user.id, job_id=ctx.job_id,
                                        reference_images=reference_images)
    if meta.get("sources"):
        for s in deck.slides:
            if s.layout not in ("cover", "section"):
                s.sources = [dict(src) for src in meta["sources"][:2]]
    await ctx.progress(45, "Checking content quality")
    content_fixes = await pipeline.pre_render_qc(ai, deck, budgets, context_text=context_text, grade=course.grade,
                                                 owner_id=user.id, job_id=ctx.job_id)
    await ctx.progress(55, "Finding images")
    async with get_sessionmaker()() as db:
        used_images = await usage.used(db, user.id, "ai_images", usage.period_start(None))
        images, img_counts = await asset_svc.resolve_images(
            db, owner_id=user.id, slides=deck.slides, colors=spec["colors"], job_id=ctx.job_id,
            allow_ai_images=max(0, min(4, ai_image_allowance - used_images)),
            source_images=image_catalog, image_mode=course.options.get("image_mode", "auto"),
            teaching_context=f"Grade {course.grade} {course.subject}; topic {course.topic}; slide {lesson.title}; preferred image style: {prefs.get('preferred_image_style', 'as requested in the visual description')}")
        if img_counts["ai"]:
            await usage.consume(db, user.id, img_counts["ai"], "ai_image", str(lesson_id), resource="ai_images")
        await db.commit()
        core_props = await _core_props(db, user, course, lesson)

    async def _stage(msg: str) -> None:
        await ctx.progress(70, msg)

    await ctx.progress(65, "Building your PowerPoint")
    outcome = await pipeline.render_with_qc(
        ai, base_pptx=base, template_spec=spec, deck=deck, budgets=budgets, images=images, language=course.language,
        core_props=core_props, context_text=context_text, grade=course.grade,
        min_font_pt=float(qc_settings.get("min_body_pt", 16)), max_rounds=int(qc_settings.get("max_repair_attempts", 2)),
        owner_id=user.id, job_id=ctx.job_id, on_progress=_stage)
    await ctx.progress(80, "Visual quality check")
    try:
        visual = await asyncio.to_thread(inspect, outcome.pptx)
        if visual.failing_slides:
            for n in visual.failing_slides:
                deck.slides[n - 1] = pipeline.enforce_budgets(deck.slides[n - 1], budgets, strict=True)
            outcome = await pipeline.render_with_qc(
                ai, base_pptx=base, template_spec=spec, deck=deck, budgets=budgets, images=images,
                language=course.language, core_props=core_props, context_text=context_text, grade=course.grade,
                min_font_pt=float(qc_settings.get("min_body_pt", 16)), max_rounds=0, owner_id=user.id,
                job_id=ctx.job_id)
            visual = await asyncio.to_thread(inspect, outcome.pptx)
    except RenderError as e:
        log(logger, logging.WARNING, "visual_qc_unavailable", error=str(e))
        visual = None

    await ctx.progress(92, "Saving")
    result = await save_lesson_output(lesson_id, deck, outcome.pptx, visual, qc={
        "render": outcome.reports, "repairs": outcome.repairs, "content_fixes": content_fixes, "images": img_counts,
        "visual": {str(k): v for k, v in (visual.issues.items() if visual else [])},
        "ai_mode": ai.mode, "content_quality": {"status": "structural_checks_passed",
            "reference_count": reference_count(meta.get("sources", [])), "fact_check_status": "teacher_review_required"}})
    async with get_sessionmaker()() as db:
        await usage.consume(db, user.id, await usage.credit_cost("slide", len(deck.slides)), "lesson_generation",
                            str(lesson_id))
        concepts = ", ".join(plan.lectures[lesson.number - 1].key_concepts)
        await memory_svc.add_memory(
            db, user.id, "lesson_summary",
            f"{course.topic} lesson {lesson.number} ({lesson.title}) for Grade {course.grade}: introduced {concepts}. "
            f"Homework: {deck.lesson_plan.homework.task}",
            meta={"course_id": str(course.id), "lesson_number": lesson.number},
            class_section_id=course.class_section_id, lesson_id=lesson.id)
        await _refresh_course_status(db, course.id)
        await db.commit()
    return result


async def save_lesson_output(lesson_id: uuid.UUID, deck: LessonDeck, pptx: bytes, visual, qc: dict[str, Any],
                             reason: str = "generated") -> dict[str, Any]:
    storage = get_storage()
    qc = {**qc, "visual_status": "checked" if visual is not None else "unavailable"}
    async with get_sessionmaker()() as db:
        lesson = await db.get(Lesson, lesson_id)
        qc.setdefault("content_quality", {"status": "structural_checks_passed",
            "reference_count": reference_count(source for slide in deck.slides for source in slide.sources),
            "fact_check_status": "teacher_review_required"})
        lesson.version += 1
        v = lesson.version
        pptx_key = f"lessons/{lesson_id}/v{v}/lesson.pptx"
        await storage.put(pptx_key, pptx)
        lesson.pptx_key = pptx_key
        lesson.pdf_key = None  # Never serve a PDF from an older version if rendering failed.
        if visual is not None:
            pdf_key = f"lessons/{lesson_id}/v{v}/lesson.pdf"
            await storage.put(pdf_key, visual.pdf, "application/pdf")
            lesson.pdf_key = pdf_key
        existing = {s.number: s for s in (await db.execute(select(Slide).where(Slide.lesson_id == lesson_id))
                                          ).scalars().all()}
        for n, s in list(existing.items()):
            if n > len(deck.slides):
                await db.delete(s)
        await db.flush()
        for spec in deck.slides:
            preview_key = None
            if visual is not None and spec.number - 1 < len(visual.previews):
                preview_key = f"lessons/{lesson_id}/v{v}/slide_{spec.number}.png"
                await storage.put(preview_key, visual.previews[spec.number - 1], "image/png")
            render_rep = next((r for r in qc.get("render", []) if r["number"] == spec.number), {})
            slide_qc = {"overflow": render_rep.get("overflow", False), "min_font_pt": render_rep.get("min_font_pt"),
                        "visual": (qc.get("visual") or {}).get(str(spec.number), [])}
            row = existing.get(spec.number)
            data = spec.model_dump()
            if row is None:
                row = Slide(lesson_id=lesson_id, number=spec.number, spec=data, qc=slide_qc, preview_key=preview_key)
                db.add(row)
                await db.flush()
            else:
                if row.spec != data:
                    row.version += 1
                row.spec, row.qc, row.preview_key = data, slide_qc, preview_key
            db.add(SlideVersion(slide_id=row.id, version=row.version, spec=data, reason=reason))
        lesson.plan = deck.lesson_plan.model_dump()
        lesson.title = deck.lesson_plan.title or lesson.title
        lesson.qc_report = qc
        if lesson.status in ("planned", "generating", "failed", "generated"):
            lesson.status = "generated"
        lesson.error = None
        await db.commit()
        failing = [r["number"] for r in qc.get("render", []) if r.get("overflow")]
        return {"lesson_id": str(lesson_id), "version": v, "slides": len(deck.slides), "overflow": failing}


async def _refresh_course_status(db: AsyncSession, course_id: uuid.UUID) -> None:
    course = await db.get(Course, course_id)
    statuses = [s for (s,) in (await db.execute(select(Lesson.status).where(Lesson.course_id == course_id))).all()]
    if statuses and all(s in ("generated", "taught", "reflected", "skipped") for s in statuses):
        course.status = "ready"
    elif any(s == "generating" for s in statuses):
        course.status = "generating"
    elif any(s == "failed" for s in statuses):
        course.status = "partial"
    else:
        course.status = "planned"
    project = await db.get(Project, course.project_id)
    project.status = course.status


async def on_lesson_failed(ctx: JobContext, error: str) -> None:
    async with get_sessionmaker()() as db:
        lesson = await db.get(Lesson, uuid.UUID(ctx.payload["lesson_id"]))
        if lesson:
            lesson.status = "failed" if not lesson.pptx_key else "generated"
            lesson.error = error[:2000]
            await _refresh_course_status(db, lesson.course_id)
            await db.commit()


# --------------------------------------------------------------------------- slide editing


async def load_deck(db: AsyncSession, lesson: Lesson) -> LessonDeck:
    slides = (await db.execute(select(Slide).where(Slide.lesson_id == lesson.id).order_by(Slide.number))
              ).scalars().all()
    if not slides or not lesson.plan:
        raise AppError("not_generated", "This lesson has not been generated yet.", 409)
    return LessonDeck(lesson_plan=LessonPlan.model_validate(lesson.plan),
                      slides=[SlideSpec.model_validate(s.spec) for s in slides])


async def rerender_lesson(lesson_id: uuid.UUID, deck: LessonDeck, *, reason: str, owner_id: uuid.UUID,
                          job_id: uuid.UUID | None = None) -> dict[str, Any]:
    ai = get_ai()
    async with get_sessionmaker()() as db:
        lesson = await db.get(Lesson, lesson_id)
        course = await db.get(Course, lesson.course_id)
        user = await db.get(User, owner_id)
        template = await resolve_template(db, owner_id, course.template_id)
        base = await get_storage().get(template.base_storage_key)
        spec = template.spec
        if course.options.get("image_mode") == "stock":
            images, _ = await asset_svc.resolve_images(db, owner_id=owner_id, slides=deck.slides,
                colors=spec["colors"], job_id=job_id, image_mode="stock")
            await db.commit()
        else:
            images = await asset_svc.load_images(db, deck.slides)
        missing = [s for s in deck.slides if s.visual.kind != "none" and s.layout in ("image_text", "concept")
                   and not s.asset_id]
        if missing:
            new_images, _ = await asset_svc.resolve_images(db, owner_id=owner_id, slides=missing,
                                                           colors=spec["colors"], job_id=job_id, image_mode=course.options.get("image_mode", "auto"))
            images.update(new_images)
            await db.commit()
        core_props = await _core_props(db, user, course, lesson)
    budgets = compute_budgets(spec)
    outcome = await pipeline.render_with_qc(ai, base_pptx=base, template_spec=spec, deck=deck, budgets=budgets,
                                            images=images, language=course.language, core_props=core_props,
                                            context_text="", grade=course.grade, owner_id=owner_id, job_id=job_id, max_rounds=0)
    try:
        visual = await asyncio.to_thread(inspect, outcome.pptx)
    except RenderError:
        visual = None
    return await save_lesson_output(lesson_id, deck, outcome.pptx, visual, qc={
        "render": outcome.reports, "repairs": outcome.repairs,
        "visual": {str(k): v for k, v in (visual.issues.items() if visual else [])}, "ai_mode": ai.mode},
        reason=reason)


async def handle_slide_regeneration(ctx: JobContext) -> dict[str, Any]:
    lesson_id = uuid.UUID(ctx.payload["lesson_id"])
    number = int(ctx.payload["slide_number"])
    instruction = ctx.payload["instruction"]
    ai = get_ai()
    async with get_sessionmaker()() as db:
        lesson = await db.get(Lesson, lesson_id)
        course = await db.get(Course, lesson.course_id)
        user = await db.get(User, lesson.owner_id)
        deck = await load_deck(db, lesson)
        template = await resolve_template(db, user.id, course.template_id)
        budgets = compute_budgets(template.spec)
        context_text, _ = await build_context(db, user, topic=course.topic, class_section_id=course.class_section_id,
                                              subject=course.subject, source_file_ids=course.options.get("source_file_ids"))
    await ctx.progress(20, "Rewriting the slide")
    old = next((slide for slide in deck.slides if slide.number == number), None)
    if old is None:
        raise PermanentJobError("This slide no longer exists.")
    keep_images = ctx.payload.get("keep_images", True)
    if keep_images:
        instruction += "\nPreserve the existing visual, picture, image references and quantities. Change only the requested content; keep all other facts and fields consistent."
    new = await pipeline.repair_slide(ai, old, instruction, budgets, context_text=context_text, grade=course.grade,
                                      owner_id=user.id, job_id=ctx.job_id, tier="content")
    if keep_images:
        new.visual, new.asset_id = old.visual.model_copy(deep=True), old.asset_id
        new.sources = list(old.sources)
    elif new.visual.kind == "none" or new.visual.description != old.visual.description:
        new.asset_id = None  # a different picture is needed (resolved again on re-render)
    new = pipeline.enforce_budgets(new, budgets)
    if new.model_dump() == old.model_dump():
        return {"lesson_id": str(lesson_id), "changed": False, "credits_used": 0}
    deck.slides[deck.slides.index(old)] = new
    await ctx.progress(60, "Rebuilding the PowerPoint")
    result = await rerender_lesson(lesson_id, deck, reason=f"regenerated: {instruction[:80]}", owner_id=user.id,
                                   job_id=ctx.job_id)
    cost = ctx.payload.get("credit_cost")
    if cost is None:
        cost = await usage.credit_cost("slide")
    async with get_sessionmaker()() as db:
        await usage.consume(db, user.id, cost, "slide_regeneration", str(lesson_id))
        await db.commit()
    return {**result, "changed": True, "credits_used": cost}


async def handle_lesson_render(ctx: JobContext) -> dict[str, Any]:
    lesson_id = uuid.UUID(ctx.payload["lesson_id"])
    async with get_sessionmaker()() as db:
        lesson = await db.get(Lesson, lesson_id)
        deck = await load_deck(db, lesson)
        owner = lesson.owner_id
    await ctx.progress(30, "Rebuilding the PowerPoint")
    return await rerender_lesson(lesson_id, deck, reason=ctx.payload.get("reason", "edited"), owner_id=owner,
                                 job_id=ctx.job_id)


async def edit_slide(db: AsyncSession, user: User, lesson_id: uuid.UUID, number: int,
                     spec_data: dict[str, Any]) -> uuid.UUID:
    await usage.lock_user(db, user.id)
    lesson = await get_owned(db, Lesson, lesson_id, user)
    if await pending_lesson_edit(db, user.id, lesson_id):
        raise AppError("edit_pending", "Wait for the current lesson update to finish before editing again.", 409)
    row = (await db.execute(select(Slide).where(Slide.lesson_id == lesson_id, Slide.number == number))
           ).scalars().first()
    if row is None:
        raise NotFound("Slide")
    before = dict(row.spec)
    merged = {**row.spec, **spec_data, "number": number}
    if "visual" in spec_data and "asset_id" not in spec_data and spec_data["visual"] != row.spec.get("visual"):
        merged["asset_id"] = None
    if merged.get("asset_id"):
        try:
            asset = await db.get(Asset, uuid.UUID(merged["asset_id"]))
        except ValueError:
            asset = None
        if asset is None or asset.owner_id not in (user.id, None):
            raise NotFound("Image")
    try:
        spec = SlideSpec.model_validate(merged)
    except ValidationError as exc:
        raise AppError("invalid_slide", "Check the slide fields: " + str(exc)[:600], 400) from exc
    row.spec = spec.model_dump()
    row.version += 1
    db.add(SlideVersion(slide_id=row.id, version=row.version, spec=row.spec, reason="teacher edit"))
    await memory_svc.learn_from_slide_edit(db, user.id, before, row.spec)
    job = await enqueue(db, "lesson_render", {"lesson_id": str(lesson.id), "reason": "teacher edit"},
                        owner_id=user.id)
    await db.commit()
    await run_inline_if_configured([job.id])
    return job.id


async def restore_slide_version(db: AsyncSession, user: User, lesson_id: uuid.UUID, number: int,
                                version: int) -> uuid.UUID:
    row = (await db.execute(select(Slide).where(Slide.lesson_id == lesson_id, Slide.number == number))
           ).scalars().first()
    if row is None:
        raise NotFound("Slide")
    await get_owned(db, Lesson, lesson_id, user)
    ver = (await db.execute(select(SlideVersion).where(SlideVersion.slide_id == row.id, SlideVersion.version == version)
                            )).scalars().first()
    if ver is None:
        raise NotFound("Slide version")
    return await edit_slide(db, user, lesson_id, number, ver.spec)


async def regenerate_slide(db: AsyncSession, user: User, lesson_id: uuid.UUID, number: int, *,
                           action: str | None, instruction: str | None, keep_images: bool = True) -> uuid.UUID:
    await usage.lock_user(db, user.id)
    await get_owned(db, Lesson, lesson_id, user)
    text = QUICK_ACTIONS.get(action or "", "") + (" " + instruction if instruction else "")
    if not text.strip():
        raise AppError("bad_request", "Choose an action or describe the change.", 400)
    row = (await db.execute(select(Slide).where(Slide.lesson_id == lesson_id, Slide.number == number))).scalars().first()
    if row is None:
        raise NotFound("Slide")
    pending = await pending_lesson_edit(db, user.id, lesson_id)
    if pending:
        if (pending.type == "slide_regeneration" and pending.payload.get("slide_number") == number
                and pending.payload.get("instruction") == text.strip()
                and pending.payload.get("keep_images", True) == keep_images):
            return pending.id
        raise AppError("edit_pending", "Wait for the current lesson update to finish before editing again.", 409)
    cost = await usage.credit_cost("slide")
    await usage.check(db, user, "credits", cost, jobs=1)
    job = await enqueue(db, "slide_regeneration", {"lesson_id": str(lesson_id), "slide_number": number,
                                                   "instruction": text.strip(), "keep_images": keep_images, "credit_cost": cost}, owner_id=user.id,
                        max_attempts=1, dedupe=True, credits_reserved=cost)
    await db.commit()
    await run_inline_if_configured([job.id])
    return job.id


async def course_progress(db: AsyncSession, course_id: uuid.UUID) -> dict[str, Any]:
    from app.models import GenerationJob

    lessons = (await db.execute(select(Lesson).where(Lesson.course_id == course_id).order_by(Lesson.number))
               ).scalars().all()
    out = []
    for lesson in lessons:
        job = (await db.execute(select(GenerationJob).where(
            GenerationJob.payload["lesson_id"].astext == str(lesson.id)).order_by(GenerationJob.created_at.desc())
            .limit(1))).scalars().first()
        out.append({"lesson_id": str(lesson.id), "number": lesson.number, "title": lesson.title,
                    "status": lesson.status, "progress": job.progress if job else (100 if lesson.pptx_key else 0),
                    "stage": job.stage if job else None, "error": lesson.error})
    return {"lessons": out, "done": sum(1 for x in out if x["status"] in ("generated", "taught", "reflected")),
            "total": len(out)}


async def class_active_course(db: AsyncSession, class_id: uuid.UUID) -> Course | None:
    cs = await db.get(ClassSection, class_id)
    if cs and cs.active_course_id:
        return await db.get(Course, cs.active_course_id)
    return (await db.execute(select(Course).where(Course.class_section_id == class_id)
                             .order_by(Course.created_at.desc()))).scalars().first()


async def count_lessons(db: AsyncSession, user_id: uuid.UUID) -> int:
    return (await db.execute(select(func.count()).select_from(Lesson).where(Lesson.owner_id == user_id))).scalar_one()


def now_iso() -> str:
    return utcnow().isoformat()


async def teacher_image_catalog(db: AsyncSession, owner_id: uuid.UUID, images: list[dict]) -> dict:
    catalog = {}
    for i, item in enumerate(images):
        asset = await db.get(Asset, uuid.UUID(str(item["asset_id"])))
        if asset is None or asset.owner_id != owner_id or asset.source != "upload" or asset.kind != "image":
            raise NotFound("Teacher image")
        catalog[f"teacher_image_{i + 1}"] = {"asset_id": str(asset.id), "description": item["description"],
            "teacher_supplied": True, "storage_key": asset.storage_key}
    return catalog


async def pending_lesson_edit(db: AsyncSession, owner_id: uuid.UUID, lesson_id: uuid.UUID):
    return (await db.execute(select(GenerationJob).where(
        GenerationJob.owner_id == owner_id,
        GenerationJob.type.in_(["slide_regeneration", "image_replacement", "lesson_render", "lesson_generation"]),
        GenerationJob.payload["lesson_id"].astext == str(lesson_id),
        GenerationJob.status.in_(["queued", "running"])).limit(1))).scalars().first()
