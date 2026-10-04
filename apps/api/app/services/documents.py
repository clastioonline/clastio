"""Worksheets, quizzes, tests, homework, lesson-plan and teacher-guide documents."""

from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import get_ai
from app.core.db import get_sessionmaker, utcnow
from app.core.errors import AppError
from app.core.storage import get_storage
from app.engine.exports import documents as builders
from app.engine.qc.visual import RenderError, docx_to_pdf
from app.generation import prompts
from app.generation.quality import ContentQualityError, assessment_errors
from app.generation.specs import AssessmentDoc, HomeworkDoc, LessonPlan, SlideSpec
from app.jobs.queue import JobContext, enqueue, run_inline_if_configured
from app.models import ClassSection, Course, Document, Lesson, Question, Slide, Template, User
from app.services import usage
from app.services.context import CURRICULUM_NAMES, build_context
from app.services.courses import get_owned, resolve_template

KINDS = {"worksheet", "quiz", "assessment", "homework", "lesson_plan", "teacher_guide"}
COST_KEY = {"worksheet": "worksheet", "quiz": "quiz", "assessment": "assessment", "homework": "homework",
            "lesson_plan": "lesson_plan_doc", "teacher_guide": "lesson_plan_doc"}


def lesson_material(slides: list[SlideSpec], plan: dict | None) -> str:
    parts: list[str] = []
    if plan:
        parts.append("Objectives: " + "; ".join(plan.get("objectives", [])))
    for s in slides:
        bits = [f"[{s.title}]"]
        bits += [b.text for b in s.bullets]
        bits += [f"{st.label}: {st.detail}" for st in s.steps]
        bits += [f"{t.term} = {t.meaning}" for t in s.terms]
        for c in s.columns:
            bits.append(f"{c.heading}: " + ", ".join(c.bullets))
        if s.quiz:
            bits.append(f"Q: {s.quiz.question}")
        parts.append(" | ".join(bits))
    return "\n".join(parts)[:9000]


async def _material(db: AsyncSession, user: User, doc: Document, scope: str | None) -> tuple[str, list[dict], dict]:
    """Collect what students were taught for this document."""
    lessons: list[Lesson] = []
    if doc.lesson_id:
        lessons = [await db.get(Lesson, doc.lesson_id)]
    elif doc.course_id:
        q = select(Lesson).where(Lesson.course_id == doc.course_id)
        if scope == "taught":
            q = q.where(Lesson.status.in_(["taught", "reflected"]))
        lessons = list((await db.execute(q.order_by(Lesson.number))).scalars().all())
    elif scope == "month":
        since = utcnow() - timedelta(days=31)
        lessons = list((await db.execute(select(Lesson).where(
            Lesson.owner_id == user.id, Lesson.status.in_(["generated", "taught", "reflected"]),
            Lesson.updated_at >= since).order_by(Lesson.updated_at))).scalars().all())
    texts, slides_all, info = [], [], {}
    for lesson in lessons:
        slides = [SlideSpec.model_validate(s.spec) for s in (await db.execute(
            select(Slide).where(Slide.lesson_id == lesson.id).order_by(Slide.number))).scalars().all()]
        slides_all += [s.model_dump() for s in slides]
        texts.append(f"LESSON {lesson.number}: {lesson.title}\n" + lesson_material(slides, lesson.plan))
        course = await db.get(Course, lesson.course_id)
        info = {"topic": course.topic, "grade": course.grade, "subject": course.subject,
                "curriculum": course.curriculum, "class_section_id": course.class_section_id,
                "language": course.language}
    return "\n\n".join(texts)[:14000], slides_all, info


async def create_document(db: AsyncSession, user: User, data: dict[str, Any]) -> tuple[Document, uuid.UUID]:
    kind = data["kind"]
    if kind not in KINDS:
        raise AppError("bad_request", "Unknown document type", 400)
    lesson_id, course_id = data.get("lesson_id"), data.get("course_id")
    if lesson_id:
        lesson = await get_owned(db, Lesson, lesson_id, user)
        course_id = course_id or lesson.course_id
        if kind in ("lesson_plan", "teacher_guide") and not lesson.plan:
            raise AppError("not_generated", "Generate the lesson first.", 409)
    if course_id:
        await get_owned(db, Course, course_id, user)
    if not (lesson_id or course_id or data.get("scope") == "month" or data.get("topic")):
        raise AppError("bad_request", "Choose a lesson, a course, a scope or a topic.", 400)
    cost = await usage.credit_cost(COST_KEY[kind])
    await usage.check(db, user, "credits", cost, jobs=1)
    topic = data.get("topic") or (lesson.title if lesson_id else "")
    title = data.get("title") or (kind.replace("_", " ").title() + (f" · {topic}" if topic else ""))
    title = title[:300]
    doc = Document(owner_id=user.id, lesson_id=lesson_id if kind != "assessment" or not data.get("scope") else None,
                   course_id=course_id, kind=kind, title=title, difficulty=data.get("difficulty", "mixed"),
                   content={"options": {k: v for k, v in data.items() if k not in ("kind",)}}, status="queued")
    db.add(doc)
    await db.flush()
    job = await enqueue(db, "document_generation", {"document_id": str(doc.id)}, owner_id=user.id,
                        credits_reserved=cost)
    await db.commit()
    await run_inline_if_configured([job.id])
    return doc, job.id


async def handle_document_generation(ctx: JobContext) -> dict[str, Any]:
    doc_id = uuid.UUID(ctx.payload["document_id"])
    storage = get_storage()
    ai = get_ai()
    async with get_sessionmaker()() as db:
        doc = await db.get(Document, doc_id)
        user = await db.get(User, doc.owner_id)
        opts = (doc.content or {}).get("options", {})
        material, slides_all, info = await _material(db, user, doc, opts.get("scope"))
        topic = info.get("topic") or opts.get("topic") or doc.title
        template: Template | None = await resolve_template(db, user.id, None)
        accent = (template.spec["colors"]["primary"] if template else "#1D4ED8")
        font = (template.spec["fonts"]["body"] if template else "Calibri")
        class_name = ""
        if info.get("class_section_id"):
            cs = await db.get(ClassSection, info["class_section_id"])
            class_name = cs.name if cs else ""
        subtitle = " • ".join(x for x in (f"Grade {info['grade']}" if info.get("grade") else "",
                                          info.get("subject", ""), class_name, topic) if x)
        doc.status = "processing"
        await db.commit()
        lesson = await db.get(Lesson, doc.lesson_id) if doc.lesson_id else None
        course = await db.get(Course, doc.course_id) if doc.course_id else None

    files: dict[str, str] = {}
    content: dict[str, Any] = {"options": opts}
    prefix = f"documents/{doc_id}"
    await ctx.progress(15, "Preparing")

    if doc.kind in ("lesson_plan", "teacher_guide"):
        plan = LessonPlan.model_validate(lesson.plan)
        if doc.kind == "lesson_plan":
            local = (course.plan or {}).get("local_context_links", []) if course else []
            data = builders.lesson_plan_docx(plan, meta={
                "teacher": user.name, "class": class_name, "subject": info.get("subject", ""),
                "grade": info.get("grade", ""),
                "curriculum": CURRICULUM_NAMES.get(info.get("curriculum", ""), info.get("curriculum", "")),
                "total": course.num_lectures if course else "", "date": str(lesson.scheduled_date or ""),
                "local_links": local}, accent=accent, font=font,
                outcomes=[o.get("text") for o in (course.options.get("outcomes") or [])] if course else None)
        else:
            data = builders.teacher_guide_docx([SlideSpec.model_validate(s) for s in slides_all], plan,
                                               title=lesson.title, accent=accent, font=font)
        files["docx"] = f"{prefix}/{doc.kind}.docx"
        await storage.put(files["docx"], data)
    else:
        await ctx.progress(30, "Writing questions")
        async with get_sessionmaker()() as db:
            context_text, _ = await build_context(db, user, topic=topic,
                                                  class_section_id=info.get("class_section_id"),
                                                  subject=info.get("subject"), include_sources=True)
            prev = (await db.execute(select(Question.stem).where(
                Question.owner_id == user.id, Question.class_section_id == info.get("class_section_id"))
                .order_by(Question.created_at.desc()).limit(40))).scalars().all() if info.get("class_section_id") \
                else []
        n = int(opts.get("num_questions") or (5 if doc.kind == "homework" else 10))
        options = {"num_questions": n, "difficulty": doc.difficulty,
                   "question_types": opts.get("question_types") or ["mcq", "true_false", "short_answer",
                                                                     "fill_blank", "application"],
                   "include_case_study": bool(opts.get("include_case_study")), "grade": info.get("grade"),
                   "avoid_questions_already_used": list(prev)[:40],
                   "instructions": opts.get("instructions"),
                   "tiered": doc.difficulty == "tiered"}
        if not material:
            material = f"Topic: {topic}. Grade {info.get('grade') or opts.get('grade', '')}."
        schema = HomeworkDoc if doc.kind == "homework" else AssessmentDoc
        assessment_prompt = prompts.assessment_prompt(kind=doc.kind, context_text=context_text, material=material,
                                                       options=options)
        generation_context = {"topic": topic, "num_questions": n, "kind": doc.kind, "slides": slides_all,
                              "include_case_study": options["include_case_study"]}
        result = await ai.structured(
            task="assessment", tier="content", system=prompts.ASSESSMENT_SYSTEM,
            prompt=assessment_prompt,
            schema=schema, effort="low", owner_id=user.id, job_id=ctx.job_id,
            offline_context=generation_context,
            prompt_version=prompts.PROMPT_VERSION)
        quality_issues = assessment_errors(result, n)
        if quality_issues and ai.mode == "live":
            result = await ai.structured(task="assessment", tier="content", system=prompts.ASSESSMENT_SYSTEM,
                prompt=assessment_prompt + "\n\nCorrect these checks and return the complete assessment:\n" + "\n".join(quality_issues[:20]),
                schema=schema, effort="low", owner_id=user.id, job_id=ctx.job_id,
                offline_context=generation_context, prompt_version=prompts.PROMPT_VERSION)
        if assessment_errors(result, n):
            raise ContentQualityError("The assessment did not pass its question-count and answer-key checks. No worksheet was published. Review the brief and try again.")
        content["quality"] = {"status": "structural_checks_passed", "fact_check_status": "teacher_review_required"}
        await ctx.progress(65, "Formatting documents")
        rtl = (info.get("language") or "en") in ("ar", "ur")
        if isinstance(result, HomeworkDoc):
            student = builders.homework_docx(result, subtitle=subtitle, accent=accent, font=font, key=False, rtl=rtl)
            key = builders.homework_docx(result, subtitle=subtitle, accent=accent, font=font, key=True, rtl=rtl)
        else:
            student = builders.assessment_docx(result, subtitle=subtitle, accent=accent, font=font, key=False,
                                               rtl=rtl)
            key = builders.assessment_docx(result, subtitle=subtitle, accent=accent, font=font, key=True, rtl=rtl)
        files["docx"] = f"{prefix}/student.docx"
        files["key_docx"] = f"{prefix}/answer_key.docx"
        await storage.put(files["docx"], student)
        await storage.put(files["key_docx"], key)
        questions = builders.all_questions(result)
        if doc.kind in ("quiz", "worksheet", "assessment"):
            files["csv"] = f"{prefix}/quiz_kahoot.csv"
            files["gift"] = f"{prefix}/quiz_moodle.gift.txt"
            await storage.put(files["csv"], builders.kahoot_csv(questions), "text/csv")
            await storage.put(files["gift"], builders.moodle_gift(questions, result.title), "text/plain")
        content["data"] = result.model_dump()
        async with get_sessionmaker()() as db:
            for q in questions:
                db.add(Question(owner_id=user.id, course_id=doc.course_id, lesson_id=doc.lesson_id,
                                class_section_id=info.get("class_section_id"), qtype=q.qtype, difficulty=q.difficulty,
                                bloom=q.bloom, stem=q.stem, options=q.options, answer=q.answer,
                                explanation=q.explanation, used_count=1))
            await db.commit()
    await ctx.progress(80, "Creating PDFs")
    for src, dst in (("docx", "pdf"), ("key_docx", "key_pdf")):
        if src in files:
            try:
                pdf = await asyncio.to_thread(docx_to_pdf, await storage.get(files[src]))
                files[dst] = files[src].rsplit(".", 1)[0] + ".pdf"
                await storage.put(files[dst], pdf, "application/pdf")
            except RenderError:
                pass
    async with get_sessionmaker()() as db:
        doc = await db.get(Document, doc_id)
        doc.files, doc.content, doc.status = files, content, "ready"
        if content.get("data", {}).get("title"):
            doc.title = content["data"]["title"]
        await usage.consume(db, user.id, await usage.credit_cost(COST_KEY[doc.kind]), doc.kind, str(doc_id))
        await db.commit()
    return {"document_id": str(doc_id), "files": list(files)}


async def on_document_failed(ctx: JobContext, error: str) -> None:
    async with get_sessionmaker()() as db:
        doc = await db.get(Document, uuid.UUID(ctx.payload["document_id"]))
        if doc:
            doc.status = "failed"
            doc.content = {**(doc.content or {}), "error": error[:1000]}
            await db.commit()
