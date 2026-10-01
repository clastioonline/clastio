from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date
from typing import Any
from urllib.parse import unquote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sse_starlette.sse import EventSourceResponse

from app.core.db import get_sessionmaker
from app.core.deps import DB, CurrentUser, can_access
from app.core.errors import AppError, NotFound
from app.core.ratelimit import rate_limit
from app.core.security import verify_signed_value
from app.core.storage import LocalStorage, get_storage
from app.generation.specs import CoursePlan
from app.jobs.queue import enqueue, run_inline_if_configured
from app.models import (
    ClassSection,
    Course,
    Document,
    GenerationJob,
    Lesson,
    LessonReflection,
    Project,
    Question,
    Slide,
    SlideVersion,
    StyleProfile,
    TeacherProfile,
    Template,
    UploadedFile,
)
from app.services import courses as course_svc
from app.services import documents as doc_svc
from app.services import planner, usage
from app.services.uploads import store_upload

router = APIRouter(tags=["content"])


def signed(key: str | None, filename: str | None = None) -> str | None:
    return get_storage().signed_url(key, filename) if key else None


# --------------------------------------------------------------------------- uploads


def upload_out(f: UploadedFile) -> dict[str, Any]:
    return {"id": str(f.id), "filename": f.filename, "kind": f.kind, "size_bytes": f.size_bytes, "status": f.status,
            "stage": f.stage, "error": f.error, "page_count": f.page_count, "created_at": f.created_at.isoformat()}


async def upload_limit_mb(db, user) -> int:
    """The smallest of: the server cap, the admin's platform cap and the teacher's plan cap."""
    from app.core.config import get_settings
    from app.services.settings import get_setting_cached

    caps = [get_settings().max_upload_mb, int((await get_setting_cached("system")).get("max_upload_mb", 100))]
    if user.role != "admin":
        plan_cap = (await usage.plan_limits(db, user)).get("max_upload_mb")
        if plan_cap:
            caps.append(int(plan_cap))
    return max(1, min(caps))


async def read_limited(file: UploadFile, limit_mb: int) -> bytes:
    """Read the upload in chunks and stop as soon as it passes the limit, so a huge file can't exhaust memory."""
    limit = limit_mb * 1024 * 1024
    if file.size is not None and file.size > limit:
        raise AppError("file_too_large", f"Files must be smaller than {limit_mb} MB on your plan.", 413)
    chunks, total = [], 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > limit:
            raise AppError("file_too_large", f"Files must be smaller than {limit_mb} MB on your plan.", 413)
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/uploads", dependencies=[Depends(rate_limit("upload", 20, 3600))])
async def upload(user: CurrentUser, db: DB, file: UploadFile = File(...), kind: str = Form("style"),
                 name: str | None = Form(None), rights_confirmed: bool = Form(False)):
    if kind not in ("style", "source"):
        raise AppError("bad_request", "kind must be style or source", 400)
    if kind == "style":
        await usage.check_count_limit(db, user, "style_profiles")
    data = await read_limited(file, await upload_limit_mb(db, user))
    await usage.check_storage(db, user, len(data))
    row, is_new = await store_upload(db, owner_id=user.id, filename=file.filename or "upload", data=data, kind=kind,
                                     rights_confirmed=rights_confirmed)
    job_id = None
    if is_new or row.status == "failed":
        job_type = "style_analysis" if kind == "style" else "source_indexing"
        job = await enqueue(db, job_type, {"file_id": str(row.id), "name": name}, owner_id=user.id)
        job_id = job.id
        row.status, row.stage, row.error = "queued", "Queued", None
    await db.commit()
    if job_id:
        await run_inline_if_configured([job_id])
        await db.refresh(row)
    return {"file": upload_out(row), "job_id": str(job_id) if job_id else None, "duplicate": not is_new}


@router.get("/uploads")
async def list_uploads(user: CurrentUser, db: DB, kind: str | None = None):
    q = select(UploadedFile).where(UploadedFile.owner_id == user.id)
    if kind:
        q = q.where(UploadedFile.kind == kind)
    rows = (await db.execute(q.order_by(UploadedFile.created_at.desc()))).scalars().all()
    return {"items": [upload_out(f) for f in rows]}


@router.get("/uploads/{file_id}")
async def get_upload(file_id: uuid.UUID, user: CurrentUser, db: DB):
    f = await course_svc.get_owned(db, UploadedFile, file_id, user)
    tpl = (await db.execute(select(Template).join(StyleProfile, Template.style_profile_id == StyleProfile.id)
                            .where(StyleProfile.source_file_id == f.id))).scalars().first()
    return {"file": upload_out(f), "template_id": str(tpl.id) if tpl else None}


@router.delete("/uploads/{file_id}")
async def delete_upload(file_id: uuid.UUID, user: CurrentUser, db: DB):
    f = await course_svc.get_owned(db, UploadedFile, file_id, user)
    await get_storage().delete(f.storage_key)
    await db.delete(f)
    await db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- templates


def template_out(t: Template, default_id: uuid.UUID | None = None, full: bool = False) -> dict[str, Any]:
    spec = t.spec or {}
    out = {"id": str(t.id), "name": t.name, "mode": t.mode, "builtin": t.owner_id is None, "status": t.status,
           "is_default": default_id == t.id, "created_at": t.created_at.isoformat() if t.created_at else None,
           "previews": [signed(k) for k in t.preview_keys or []],
           "colors": spec.get("colors", {}), "fonts": spec.get("fonts", {})}
    if full:
        out.update({"typography": spec.get("typography"), "zones": spec.get("zones"),
                    "corner_radius": spec.get("corner_radius"), "layouts": spec.get("layouts", []),
                    "content_style": spec.get("content_style", {}), "style_profile_id":
                        str(t.style_profile_id) if t.style_profile_id else None})
    return out


@router.get("/templates")
async def list_templates(user: CurrentUser, db: DB):
    tp = (await db.execute(select(TeacherProfile).where(TeacherProfile.user_id == user.id))).scalars().first()
    rows = (await db.execute(select(Template).where((Template.owner_id == user.id) | (Template.owner_id.is_(None)) |
                                                    ((Template.org_id == user.org_id) & Template.is_shared))
                             .order_by(Template.owner_id.is_(None), Template.created_at.desc()))).scalars().all()
    return {"items": [template_out(t, tp.default_template_id if tp else None) for t in rows]}


async def _template(db, user, template_id: uuid.UUID, write: bool = False) -> Template:
    t = await db.get(Template, template_id)
    if t is None or (t.owner_id not in (None, user.id) and not (t.is_shared and t.org_id == user.org_id)):
        raise NotFound("Template")
    if write and t.owner_id != user.id:
        raise AppError("forbidden", "Built-in templates can't be edited. Upload your own deck instead.", 403)
    return t


@router.get("/templates/{template_id}")
async def get_template(template_id: uuid.UUID, user: CurrentUser, db: DB):
    t = await _template(db, user, template_id)
    tp = (await db.execute(select(TeacherProfile).where(TeacherProfile.user_id == user.id))).scalars().first()
    out = template_out(t, tp.default_template_id if tp else None, full=True)
    if t.style_profile_id:
        sp = await db.get(StyleProfile, t.style_profile_id)
        prof = sp.profile if sp else {}
        out["analysis"] = {k: prof.get(k) for k in ("layouts_found", "content_style", "visual_rules", "stats",
                                                    "source_kind")}
    return out


class TemplatePatch(BaseModel):
    name: str | None = None
    colors: dict[str, str] | None = None
    fonts: dict[str, str] | None = None
    typography: dict[str, Any] | None = None


@router.patch("/templates/{template_id}")
async def patch_template(template_id: uuid.UUID, data: TemplatePatch, user: CurrentUser, db: DB):
    t = await _template(db, user, template_id, write=True)
    spec = dict(t.spec)
    if data.name:
        t.name = data.name
    if data.colors:
        spec["colors"] = {**spec.get("colors", {}), **{k: v for k, v in data.colors.items()
                                                       if isinstance(v, str) and v.startswith("#") and len(v) == 7}}
    if data.fonts:
        spec["fonts"] = {**spec.get("fonts", {}), **data.fonts}
    if data.typography:
        allowed = {k: float(v) for k, v in data.typography.items() if k in ("title_pt", "body_pt") and 12 <= float(v)
                   <= 60}
        spec["typography"] = {**spec.get("typography", {}), **allowed}
    t.spec = spec
    await db.commit()
    # refresh previews in the background-less way (fast: 6 slides)
    from app.services.styles import render_previews

    base = await get_storage().get(t.base_storage_key)
    t.preview_keys = await render_previews(t.id, base, spec)
    await db.commit()
    return template_out(t, full=True)


@router.post("/templates/{template_id}/default")
async def make_default(template_id: uuid.UUID, user: CurrentUser, db: DB):
    t = await _template(db, user, template_id)
    tp = (await db.execute(select(TeacherProfile).where(TeacherProfile.user_id == user.id))).scalars().first()
    tp.default_template_id = t.id
    await db.commit()
    return {"ok": True}


@router.delete("/templates/{template_id}")
async def delete_template(template_id: uuid.UUID, user: CurrentUser, db: DB):
    t = await _template(db, user, template_id, write=True)
    tp = (await db.execute(select(TeacherProfile).where(TeacherProfile.user_id == user.id))).scalars().first()
    if tp and tp.default_template_id == t.id:
        tp.default_template_id = None
    await db.delete(t)
    await db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- courses / projects


class CourseIn(BaseModel):
    topic: str = Field(min_length=2, max_length=300)
    grade: str = Field(min_length=1, max_length=20)
    subject: str = Field(min_length=1, max_length=80)
    curriculum: str | None = None
    language: str = "en"
    num_lectures: int = Field(ge=1, le=30)
    slides_per_lecture: int = Field(ge=4, le=30)
    lecture_minutes: int | None = Field(None, ge=15, le=180)
    template_id: uuid.UUID | None = None
    class_section_id: uuid.UUID | None = None
    outcomes: list[dict[str, Any]] = []
    instructions: str | None = Field(None, max_length=2000)
    auto_generate: bool = False
    homework: bool = True
    start_date: date | None = None


def lesson_out(les: Lesson, *, brief: bool = True) -> dict[str, Any]:
    out = {"id": str(les.id), "course_id": str(les.course_id), "number": les.number, "title": les.title,
           "status": les.status, "version": les.version, "error": les.error,
           "scheduled_date": les.scheduled_date.isoformat() if les.scheduled_date else None,
           "has_pptx": bool(les.pptx_key), "carry_over": les.carry_over or None}
    if not brief:
        out["plan"] = les.plan
        out["qc"] = les.qc_report
    return out


def course_out(c: Course) -> dict[str, Any]:
    return {"id": str(c.id), "project_id": str(c.project_id), "topic": c.topic, "subject": c.subject,
            "grade": c.grade, "curriculum": c.curriculum, "language": c.language, "num_lectures": c.num_lectures,
            "slides_per_lecture": c.slides_per_lecture, "lecture_minutes": c.lecture_minutes, "status": c.status,
            "error": c.error, "plan": c.plan, "template_id": str(c.template_id) if c.template_id else None,
            "class_section_id": str(c.class_section_id) if c.class_section_id else None,
            "outcome_codes": c.outcome_codes, "options": c.options, "created_at": c.created_at.isoformat()}


@router.post("/courses", dependencies=[Depends(rate_limit("create_course", 30, 3600))])
async def create_course(data: CourseIn, user: CurrentUser, db: DB):
    payload = data.model_dump()
    if payload.get("start_date"):
        payload["start_date"] = payload["start_date"].isoformat()
    if data.class_section_id:
        cs = await db.get(ClassSection, data.class_section_id)
        if cs is None or cs.user_id != user.id:
            raise NotFound("Class")
    course, job_id = await course_svc.create_course(db, user, payload)
    await db.refresh(course)
    return {"course": course_out(course), "job_id": str(job_id)}


@router.get("/projects")
async def list_projects(user: CurrentUser, db: DB, q: str | None = None, limit: int = 50):
    query = select(Project, Course).join(Course, Course.project_id == Project.id).where(Project.owner_id == user.id)
    if q:
        query = query.where(Project.title.ilike(f"%{q}%"))
    rows = (await db.execute(query.order_by(Project.created_at.desc()).limit(min(limit, 200)))).all()
    items = []
    for p, c in rows:
        lessons = (await db.execute(select(Lesson).where(Lesson.course_id == c.id).order_by(Lesson.number))
                   ).scalars().all()
        first_preview = None
        if lessons:
            s1 = (await db.execute(select(Slide.preview_key).where(Slide.lesson_id == lessons[0].id, Slide.number == 1))
                  ).scalar_one_or_none()
            first_preview = signed(s1)
        items.append({"id": str(p.id), "title": p.title, "status": c.status, "course": course_out(c),
                      "lessons_total": len(lessons),
                      "lessons_ready": sum(1 for les in lessons if les.pptx_key), "cover": first_preview,
                      "created_at": p.created_at.isoformat()})
    return {"items": items}


@router.get("/projects/{project_id}")
async def get_project(project_id: uuid.UUID, user: CurrentUser, db: DB):
    p = await course_svc.get_owned(db, Project, project_id, user)
    c = (await db.execute(select(Course).where(Course.project_id == p.id))).scalars().first()
    lessons = (await db.execute(select(Lesson).where(Lesson.course_id == c.id).order_by(Lesson.number))).scalars().all()
    out_lessons = []
    for les in lessons:
        cover = (await db.execute(select(Slide.preview_key).where(Slide.lesson_id == les.id, Slide.number == 1))
                 ).scalar_one_or_none()
        out_lessons.append({**lesson_out(les), "cover": signed(cover)})
    job = (await db.execute(select(GenerationJob).where(GenerationJob.payload["course_id"].astext == str(c.id))
                            .order_by(GenerationJob.created_at.desc()).limit(1))).scalars().first()
    return {"project": {"id": str(p.id), "title": p.title, "status": p.status}, "course": course_out(c),
            "lessons": out_lessons, "plan_job": job_out(job) if job else None,
            "progress": await course_svc.course_progress(db, c.id)}


@router.delete("/projects/{project_id}")
async def delete_project(project_id: uuid.UUID, user: CurrentUser, db: DB):
    p = await course_svc.get_owned(db, Project, project_id, user)
    await db.delete(p)
    await db.commit()
    return {"ok": True}


@router.put("/courses/{course_id}/plan")
async def update_plan(course_id: uuid.UUID, plan: CoursePlan, user: CurrentUser, db: DB):
    c = await course_svc.update_plan(db, user, course_id, plan)
    return {"course": course_out(c)}


class GenerateIn(BaseModel):
    lessons: list[int] | None = None
    instructions: str | None = Field(None, max_length=2000)


@router.post("/courses/{course_id}/generate", dependencies=[Depends(rate_limit("generate", 30, 3600))])
async def generate(course_id: uuid.UUID, data: GenerateIn, user: CurrentUser, db: DB):
    job_ids = await course_svc.start_generation(db, user, course_id, data.lessons, data.instructions)
    return {"job_ids": [str(j) for j in job_ids]}


@router.post("/courses/{course_id}/replan")
async def replan(course_id: uuid.UUID, user: CurrentUser, db: DB):
    c = await course_svc.get_owned(db, Course, course_id, user)
    c.status = "planning"
    job = await enqueue(db, "course_plan", {"course_id": str(c.id)}, owner_id=user.id)
    await db.commit()
    await run_inline_if_configured([job.id])
    return {"job_id": str(job.id)}


@router.get("/courses/{course_id}/progress")
async def progress(course_id: uuid.UUID, user: CurrentUser, db: DB):
    await course_svc.get_owned(db, Course, course_id, user)
    return await course_svc.course_progress(db, course_id)


# --------------------------------------------------------------------------- lessons & slides


def slide_out(s: Slide) -> dict[str, Any]:
    return {"id": str(s.id), "number": s.number, "version": s.version, "spec": s.spec, "qc": s.qc,
            "preview": signed(s.preview_key)}


@router.get("/lessons")
async def list_lessons(user: CurrentUser, db: DB, status: str | None = None, limit: int = 100):
    q = select(Lesson, Course).join(Course, Course.id == Lesson.course_id).where(Lesson.owner_id == user.id)
    if status:
        q = q.where(Lesson.status == status)
    rows = (await db.execute(q.order_by(Lesson.updated_at.desc()).limit(min(limit, 300)))).all()
    return {"items": [{**lesson_out(les), "topic": c.topic, "grade": c.grade, "subject": c.subject,
                       "project_id": str(c.project_id)} for les, c in rows]}


@router.get("/lessons/{lesson_id}")
async def get_lesson(lesson_id: uuid.UUID, user: CurrentUser, db: DB):
    les = await course_svc.get_owned(db, Lesson, lesson_id, user)
    c = await db.get(Course, les.course_id)
    slides = (await db.execute(select(Slide).where(Slide.lesson_id == les.id).order_by(Slide.number))).scalars().all()
    docs = (await db.execute(select(Document).where(Document.lesson_id == les.id).order_by(Document.created_at.desc()))
            ).scalars().all()
    refl = (await db.execute(select(LessonReflection).where(LessonReflection.lesson_id == les.id)
                             .order_by(LessonReflection.created_at.desc()))).scalars().all()
    job = (await db.execute(select(GenerationJob).where(GenerationJob.payload["lesson_id"].astext == str(les.id))
                            .order_by(GenerationJob.created_at.desc()).limit(1))).scalars().first()
    safe_name = "".join(ch for ch in f"{c.topic} L{les.number}" if ch.isalnum() or ch in " -_").strip()
    return {"lesson": lesson_out(les, brief=False), "course": course_out(c), "slides": [slide_out(s) for s in slides],
            "documents": [document_out(d) for d in docs],
            "reflections": [{"outcome": r.outcome, "note": r.note, "created_at": r.created_at.isoformat()} for r in refl],
            "downloads": {"pptx": signed(les.pptx_key, f"{safe_name}.pptx"),
                          "pdf": signed(les.pdf_key, f"{safe_name}.pdf")},
            "job": job_out(job) if job else None}


class LessonPatch(BaseModel):
    scheduled_date: date | None = None
    status: str | None = Field(None, pattern="^(planned|generated|taught)$")
    title: str | None = None


@router.patch("/lessons/{lesson_id}")
async def patch_lesson(lesson_id: uuid.UUID, data: LessonPatch, user: CurrentUser, db: DB):
    les = await course_svc.get_owned(db, Lesson, lesson_id, user)
    if data.scheduled_date is not None:
        les.scheduled_date = data.scheduled_date
    if data.status:
        les.status = data.status
    if data.title:
        les.title = data.title
    await db.commit()
    return lesson_out(les)


class RegenerateLessonIn(BaseModel):
    instructions: str | None = Field(None, max_length=2000)


@router.post("/lessons/{lesson_id}/regenerate")
async def regenerate_lesson(lesson_id: uuid.UUID, data: RegenerateLessonIn, user: CurrentUser, db: DB):
    les = await course_svc.get_owned(db, Lesson, lesson_id, user)
    job_ids = await course_svc.start_generation(db, user, les.course_id, [les.number], data.instructions)
    return {"job_id": str(job_ids[0])}


class ReflectionIn(BaseModel):
    outcome: str = Field(pattern="^(went_well|ran_out_of_time|struggled|skipped)$")
    note: str | None = Field(None, max_length=2000)
    covered_until_slide: int | None = None


@router.post("/lessons/{lesson_id}/reflection")
async def reflect(lesson_id: uuid.UUID, data: ReflectionIn, user: CurrentUser, db: DB):
    return await planner.record_reflection(db, user, lesson_id, data.outcome, data.note, data.covered_until_slide)


class SlidePatch(BaseModel):
    spec: dict[str, Any]


@router.patch("/lessons/{lesson_id}/slides/{number}")
async def edit_slide(lesson_id: uuid.UUID, number: int, data: SlidePatch, user: CurrentUser, db: DB):
    job_id = await course_svc.edit_slide(db, user, lesson_id, number, data.spec)
    return {"job_id": str(job_id)}


class SlideRegenIn(BaseModel):
    action: str | None = None
    instruction: str | None = Field(None, max_length=1000)


@router.post("/lessons/{lesson_id}/slides/{number}/regenerate")
async def regenerate_slide(lesson_id: uuid.UUID, number: int, data: SlideRegenIn, user: CurrentUser, db: DB):
    job_id = await course_svc.regenerate_slide(db, user, lesson_id, number, action=data.action,
                                               instruction=data.instruction)
    return {"job_id": str(job_id)}


@router.get("/lessons/{lesson_id}/slides/{number}/versions")
async def slide_versions(lesson_id: uuid.UUID, number: int, user: CurrentUser, db: DB):
    await course_svc.get_owned(db, Lesson, lesson_id, user)
    s = (await db.execute(select(Slide).where(Slide.lesson_id == lesson_id, Slide.number == number))).scalars().first()
    if s is None:
        raise NotFound("Slide")
    vs = (await db.execute(select(SlideVersion).where(SlideVersion.slide_id == s.id)
                           .order_by(SlideVersion.version.desc()))).scalars().all()
    return {"items": [{"version": v.version, "reason": v.reason, "created_at": v.created_at.isoformat(),
                       "title": v.spec.get("title")} for v in vs]}


class RestoreIn(BaseModel):
    version: int


@router.post("/lessons/{lesson_id}/slides/{number}/restore")
async def restore(lesson_id: uuid.UUID, number: int, data: RestoreIn, user: CurrentUser, db: DB):
    job_id = await course_svc.restore_slide_version(db, user, lesson_id, number, data.version)
    return {"job_id": str(job_id)}


@router.get("/slides/actions")
async def slide_actions():
    return {"actions": [{"key": k, "label": k.replace("_", " ").capitalize(), "instruction": v}
                        for k, v in course_svc.QUICK_ACTIONS.items()]}


# --------------------------------------------------------------------------- documents


def document_out(d: Document) -> dict[str, Any]:
    names = {"docx": "Student.docx", "pdf": "Student.pdf", "key_docx": "Answer key.docx", "key_pdf": "Answer key.pdf",
             "csv": "Kahoot-Quizizz.csv", "gift": "Moodle.gift.txt"}
    safe = "".join(ch for ch in d.title if ch.isalnum() or ch in " -_").strip() or d.kind
    return {"id": str(d.id), "kind": d.kind, "title": d.title, "status": d.status, "difficulty": d.difficulty,
            "lesson_id": str(d.lesson_id) if d.lesson_id else None, "course_id": str(d.course_id) if d.course_id else None,
            "created_at": d.created_at.isoformat(), "error": (d.content or {}).get("error"),
            "files": {k: signed(v, f"{safe} - {names.get(k, k)}") for k, v in (d.files or {}).items()},
            "content": (d.content or {}).get("data")}


class DocumentIn(BaseModel):
    kind: str = Field(pattern="^(worksheet|quiz|assessment|homework|lesson_plan|teacher_guide)$")
    lesson_id: uuid.UUID | None = None
    course_id: uuid.UUID | None = None
    topic: str | None = None
    scope: str | None = Field(None, pattern="^(month|taught|all)$")
    difficulty: str = Field("mixed", pattern="^(easy|medium|hard|mixed|tiered)$")
    num_questions: int | None = Field(None, ge=3, le=40)
    question_types: list[str] | None = None
    include_case_study: bool = False
    instructions: str | None = Field(None, max_length=1000)
    title: str | None = None


@router.post("/documents", dependencies=[Depends(rate_limit("documents", 60, 3600))])
async def create_document(data: DocumentIn, user: CurrentUser, db: DB):
    doc, job_id = await doc_svc.create_document(db, user, data.model_dump())
    await db.refresh(doc)
    return {"document": document_out(doc), "job_id": str(job_id)}


@router.get("/documents")
async def list_documents(user: CurrentUser, db: DB, kind: str | None = None, lesson_id: uuid.UUID | None = None):
    q = select(Document).where(Document.owner_id == user.id)
    if kind:
        q = q.where(Document.kind == kind)
    if lesson_id:
        q = q.where(Document.lesson_id == lesson_id)
    rows = (await db.execute(q.order_by(Document.created_at.desc()).limit(200))).scalars().all()
    return {"items": [document_out(d) for d in rows]}


@router.get("/documents/{doc_id}")
async def get_document(doc_id: uuid.UUID, user: CurrentUser, db: DB):
    return document_out(await course_svc.get_owned(db, Document, doc_id, user))


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: uuid.UUID, user: CurrentUser, db: DB):
    d = await course_svc.get_owned(db, Document, doc_id, user)
    await db.delete(d)
    await db.commit()
    return {"ok": True}


@router.get("/questions")
async def question_bank(user: CurrentUser, db: DB, q: str | None = None, difficulty: str | None = None,
                        class_id: uuid.UUID | None = None, limit: int = 100):
    query = select(Question).where(Question.owner_id == user.id)
    if q:
        query = query.where(Question.stem.ilike(f"%{q}%"))
    if difficulty:
        query = query.where(Question.difficulty == difficulty)
    if class_id:
        query = query.where(Question.class_section_id == class_id)
    rows = (await db.execute(query.order_by(Question.created_at.desc()).limit(min(limit, 500)))).scalars().all()
    return {"items": [{"id": str(x.id), "qtype": x.qtype, "difficulty": x.difficulty, "bloom": x.bloom,
                       "stem": x.stem, "options": x.options, "answer": x.answer, "explanation": x.explanation,
                       "used_count": x.used_count} for x in rows]}


# --------------------------------------------------------------------------- jobs


@router.get("/activity")
async def activity(user: CurrentUser, db: DB):
    from app.services.activity import summaries

    active = GenerationJob.status.in_(["queued", "running"])
    counts = dict((await db.execute(select(GenerationJob.status, func.count()).where(
        GenerationJob.owner_id == user.id).group_by(GenerationJob.status))).all())
    jobs = (await db.execute(select(GenerationJob).where(GenerationJob.owner_id == user.id).order_by(
        case((active, 0), else_=1), GenerationJob.created_at.desc()).limit(100))).scalars().all()
    return {"items": await summaries(db, list(jobs)), "active_count": counts.get("queued", 0) + counts.get("running", 0)}


def job_out(j: GenerationJob) -> dict[str, Any]:
    return {"id": str(j.id), "type": j.type, "status": j.status, "progress": j.progress, "stage": j.stage,
            "error": j.error, "result": j.result, "created_at": j.created_at.isoformat() if j.created_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None, "cost_usd": round(j.cost_usd, 4)}


@router.get("/jobs")
async def list_jobs(user: CurrentUser, db: DB, active: bool = False):
    q = select(GenerationJob).where(GenerationJob.owner_id == user.id)
    if active:
        q = q.where(GenerationJob.status.in_(["queued", "running"]))
    rows = (await db.execute(q.order_by(GenerationJob.created_at.desc()).limit(50))).scalars().all()
    return {"items": [job_out(j) for j in rows]}


@router.get("/jobs/{job_id}")
async def get_job(job_id: uuid.UUID, user: CurrentUser, db: DB):
    j = await db.get(GenerationJob, job_id)
    if j is None or not can_access(user, j.owner_id):
        raise NotFound("Job")
    return job_out(j)


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: uuid.UUID, request: Request, user: CurrentUser):
    async def gen():
        last = None
        for _ in range(1800):  # up to ~30 minutes
            if await request.is_disconnected():
                return
            async with get_sessionmaker()() as s:
                j = await s.get(GenerationJob, job_id)
                if j is None or not can_access(user, j.owner_id):
                    yield {"event": "error", "data": json.dumps({"message": "not found"})}
                    return
                data = job_out(j)
            if data != last:
                yield {"event": "progress", "data": json.dumps(data)}
                last = data
            if data["status"] in ("succeeded", "failed", "cancelled"):
                yield {"event": "done", "data": json.dumps(data)}
                return
            await asyncio.sleep(1)

    return EventSourceResponse(gen())


# --------------------------------------------------------------------------- signed file downloads (local storage)


@router.get("/files/{key:path}")
async def download(key: str, exp: int, sig: str, fn: str | None = None):
    key = unquote(key)
    if not verify_signed_value(key, exp, sig):
        raise HTTPException(status_code=403, detail="Link expired")
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        path = storage.local_path(key)
    except ValueError:  # a key that escapes the storage root
        raise HTTPException(status_code=404, detail="Not found") from None
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    import mimetypes

    ctype = mimetypes.guess_type(fn or key)[0] or "application/octet-stream"
    if key.endswith(".pptx"):
        ctype = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    elif key.endswith(".docx"):
        ctype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    headers = {"Cache-Control": "private, max-age=300"}
    if fn:
        from urllib.parse import quote

        ascii_name = fn.encode("ascii", "ignore").decode().replace('"', "") or "download"
        headers["Content-Disposition"] = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(fn)}"
    return Response(path.read_bytes(), media_type=ctype, headers=headers)
