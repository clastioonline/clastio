from __future__ import annotations

import csv
import io
import uuid
from datetime import date, time
from typing import Any

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from app.core.deps import DB, CurrentUser
from app.core.errors import AppError, NotFound
from app.models import (
    AIUsage,
    CalendarEvent,
    ClassSection,
    Course,
    Document,
    LearningOutcome,
    Lesson,
    Project,
    TeacherPreference,
    TeacherProfile,
    TimetableSlot,
    UploadedFile,
    User,
)
from app.services import memory as memory_svc
from app.services import planner, usage

router = APIRouter(tags=["teacher"])


class ProfileIn(BaseModel):
    name: str | None = None
    country: str | None = Field(None, max_length=2)
    region: str | None = None
    school_name: str | None = None
    curriculum: str | None = None
    subjects: list[str] | None = None
    grades: list[str] | None = None
    teaching_languages: list[str] | None = None
    class_duration_minutes: int | None = Field(None, ge=15, le=180)
    classes_per_day: int | None = Field(None, ge=1, le=12)
    working_days: list[int] | None = None
    teaching_style: str | None = Field(None, max_length=2000)
    locale: str | None = None
    timezone: str | None = None
    preferences: dict[str, Any] | None = None
    metadata_policy: dict[str, Any] | None = None


def profile_out(u: User, tp: TeacherProfile | None) -> dict[str, Any]:
    return {"name": u.name, "email": u.email, "locale": u.locale, "timezone": u.timezone,
            "country": tp.country if tp else "AE", "region": tp.region if tp else None,
            "school_name": tp.school_name if tp else None, "curriculum": tp.curriculum if tp else "british",
            "subjects": tp.subjects if tp else [], "grades": tp.grades if tp else [],
            "teaching_languages": tp.teaching_languages if tp else ["en"],
            "class_duration_minutes": tp.class_duration_minutes if tp else 45,
            "classes_per_day": tp.classes_per_day if tp else 5, "working_days": tp.working_days if tp else [0, 1, 2, 3, 4],
            "teaching_style": tp.teaching_style if tp else None,
            "onboarding_completed": tp.onboarding_completed if tp else False,
            "default_template_id": str(tp.default_template_id) if tp and tp.default_template_id else None,
            "metadata_policy": (tp.metadata_policy if tp else {}) or {"include_author": True, "ai_disclosure": False}}


async def _profile(db, user: User) -> TeacherProfile:
    tp = (await db.execute(select(TeacherProfile).where(TeacherProfile.user_id == user.id))).scalars().first()
    if tp is None:
        tp = TeacherProfile(user_id=user.id)
        db.add(tp)
        await db.flush()
    return tp


@router.get("/me/profile")
async def get_profile(user: CurrentUser, db: DB):
    return profile_out(user, await _profile(db, user))


@router.put("/me/profile")
async def update_profile(data: ProfileIn, user: CurrentUser, db: DB):
    tp = await _profile(db, user)
    for field in ("name", "locale", "timezone"):
        if (v := getattr(data, field)) is not None:
            setattr(user, field, v)
    for field in ("country", "region", "school_name", "curriculum", "subjects", "grades", "teaching_languages",
                  "class_duration_minutes", "classes_per_day", "working_days", "teaching_style", "metadata_policy"):
        if (v := getattr(data, field)) is not None:
            setattr(tp, field, v)
    for key, value in (data.preferences or {}).items():
        await memory_svc.set_preference(db, user.id, key, value, source="stated")
    await db.commit()
    return profile_out(user, tp)


@router.post("/me/onboarding/complete")
async def complete_onboarding(user: CurrentUser, db: DB):
    tp = await _profile(db, user)
    tp.onboarding_completed = True
    await db.commit()
    return {"ok": True}


@router.get("/me/usage")
async def my_usage(user: CurrentUser, db: DB):
    return await usage.summary(db, user)


@router.get("/me/export")
async def export_my_data(user: CurrentUser, db: DB):
    """Data portability (UAE PDPL / India DPDP): everything we store about the teacher, as JSON."""
    def rows(items, fields):
        return [{f: (str(getattr(i, f)) if getattr(i, f) is not None else None) for f in fields} for i in items]

    out: dict[str, Any] = {"user": {"email": user.email, "name": user.name, "created_at": str(user.created_at)}}
    tp = await _profile(db, user)
    out["profile"] = profile_out(user, tp)
    prefs = (await db.execute(select(TeacherPreference).where(TeacherPreference.user_id == user.id))).scalars().all()
    out["preferences"] = {p.key: p.value for p in prefs}
    out["classes"] = rows((await db.execute(select(ClassSection).where(ClassSection.user_id == user.id))).scalars(),
                          ["name", "grade", "subject", "pace", "notes"])
    out["courses"] = rows((await db.execute(select(Course).where(Course.owner_id == user.id))).scalars(),
                          ["topic", "grade", "subject", "status", "created_at"])
    out["lessons"] = rows((await db.execute(select(Lesson).where(Lesson.owner_id == user.id))).scalars(),
                          ["number", "title", "status", "scheduled_date"])
    out["documents"] = rows((await db.execute(select(Document).where(Document.owner_id == user.id))).scalars(),
                            ["kind", "title", "created_at"])
    out["uploads"] = rows((await db.execute(select(UploadedFile).where(UploadedFile.owner_id == user.id))).scalars(),
                          ["filename", "kind", "size_bytes", "created_at"])
    out["ai_usage_calls"] = len((await db.execute(select(AIUsage.id).where(AIUsage.owner_id == user.id))).all())
    return out


class DeleteIn(BaseModel):
    confirm_email: str


@router.post("/me/delete")
async def delete_account(data: DeleteIn, user: CurrentUser, db: DB):
    if data.confirm_email.lower() != user.email.lower():
        raise AppError("confirm_mismatch", "Type your email address to confirm.", 400)
    from app.core.storage import get_storage

    storage = get_storage()
    for f in (await db.execute(select(UploadedFile).where(UploadedFile.owner_id == user.id))).scalars().all():
        await storage.delete(f.storage_key)
    await db.execute(delete(Project).where(Project.owner_id == user.id))
    await db.delete(user)
    await db.commit()
    return {"deleted": True}


# --------------------------------------------------------------------------- classes


class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    grade: str
    subject: str
    curriculum: str | None = None
    pace: str = "standard"
    ability_mix: str = "mixed"
    eal_percent: int = Field(0, ge=0, le=100)
    send_notes: str | None = Field(None, max_length=1000)
    notes: str | None = Field(None, max_length=2000)
    color: str = "#2563EB"


def class_out(c: ClassSection) -> dict[str, Any]:
    return {"id": str(c.id), "name": c.name, "grade": c.grade, "subject": c.subject, "curriculum": c.curriculum,
            "pace": c.pace, "ability_mix": c.ability_mix, "eal_percent": c.eal_percent, "send_notes": c.send_notes,
            "notes": c.notes, "color": c.color,
            "active_course_id": str(c.active_course_id) if c.active_course_id else None}


@router.get("/classes")
async def list_classes(user: CurrentUser, db: DB):
    rows = (await db.execute(select(ClassSection).where(ClassSection.user_id == user.id).order_by(ClassSection.name))
            ).scalars().all()
    return {"items": [class_out(c) for c in rows]}


@router.post("/classes")
async def create_class(data: ClassIn, user: CurrentUser, db: DB):
    await usage.check_count_limit(db, user, "classes")
    c = ClassSection(user_id=user.id, **data.model_dump())
    db.add(c)
    await db.commit()
    return class_out(c)


async def _owned_class(db, user: User, class_id: uuid.UUID) -> ClassSection:
    c = await db.get(ClassSection, class_id)
    if c is None or c.user_id != user.id:
        raise NotFound("Class")
    return c


@router.put("/classes/{class_id}")
async def update_class(class_id: uuid.UUID, data: ClassIn, user: CurrentUser, db: DB):
    c = await _owned_class(db, user, class_id)
    for k, v in data.model_dump().items():
        setattr(c, k, v)
    await db.commit()
    return class_out(c)


class ActiveCourseIn(BaseModel):
    course_id: uuid.UUID | None


@router.put("/classes/{class_id}/active-course")
async def set_active_course(class_id: uuid.UUID, data: ActiveCourseIn, user: CurrentUser, db: DB):
    c = await _owned_class(db, user, class_id)
    if data.course_id:
        course = await db.get(Course, data.course_id)
        if course is None or course.owner_id != user.id:
            raise NotFound("Course")
        course.class_section_id = c.id
    c.active_course_id = data.course_id
    await db.commit()
    return class_out(c)


@router.delete("/classes/{class_id}")
async def delete_class(class_id: uuid.UUID, user: CurrentUser, db: DB):
    c = await _owned_class(db, user, class_id)
    await db.delete(c)
    await db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- timetable


class SlotIn(BaseModel):
    class_section_id: uuid.UUID
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    room: str | None = None


class TimetableIn(BaseModel):
    slots: list[SlotIn]


def slot_out(s: TimetableSlot) -> dict[str, Any]:
    return {"id": str(s.id), "class_section_id": str(s.class_section_id), "day_of_week": s.day_of_week,
            "start_time": s.start_time.strftime("%H:%M"), "end_time": s.end_time.strftime("%H:%M"), "room": s.room}


@router.get("/timetable")
async def get_timetable(user: CurrentUser, db: DB):
    rows = (await db.execute(select(TimetableSlot).where(TimetableSlot.user_id == user.id)
                             .order_by(TimetableSlot.day_of_week, TimetableSlot.start_time))).scalars().all()
    return {"slots": [slot_out(s) for s in rows]}


@router.put("/timetable")
async def replace_timetable(data: TimetableIn, user: CurrentUser, db: DB):
    own = {c for (c,) in (await db.execute(select(ClassSection.id).where(ClassSection.user_id == user.id))).all()}
    for s in data.slots:
        if s.class_section_id not in own:
            raise AppError("bad_request", "Timetable references a class you don't own.", 400)
        if s.end_time <= s.start_time:
            raise AppError("bad_request", "Each period must end after it starts.", 400)
    await db.execute(delete(TimetableSlot).where(TimetableSlot.user_id == user.id))
    for s in data.slots:
        db.add(TimetableSlot(user_id=user.id, **s.model_dump()))
    await db.commit()
    return await get_timetable(user, db)


DAY_NAMES = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


@router.post("/timetable/import")
async def import_timetable(user: CurrentUser, db: DB, file: UploadFile = File(...)):
    """CSV columns: day, start, end, class, subject, grade[, room]. Missing classes are created."""
    raw = (await file.read())[:200_000].decode("utf-8-sig", "ignore")
    reader = csv.DictReader(io.StringIO(raw))
    classes = {c.name.lower(): c for c in (await db.execute(select(ClassSection).where(
        ClassSection.user_id == user.id))).scalars().all()}
    slots = []
    for i, row in enumerate(reader, start=2):
        r = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        day = DAY_NAMES.get(r.get("day", "")[:3].lower())
        if day is None or not r.get("class"):
            raise AppError("bad_csv", f"Row {i}: need a day (Mon-Sun) and a class.", 400)
        try:
            st, en = time.fromisoformat(r["start"]), time.fromisoformat(r["end"])
        except (KeyError, ValueError) as e:
            raise AppError("bad_csv", f"Row {i}: times must look like 08:30.", 400) from e
        cs = classes.get(r["class"].lower())
        if cs is None:
            cs = ClassSection(user_id=user.id, name=r["class"], grade=r.get("grade") or "", subject=r.get("subject")
                              or "")
            db.add(cs)
            await db.flush()
            classes[r["class"].lower()] = cs
        slots.append(TimetableSlot(user_id=user.id, class_section_id=cs.id, day_of_week=day, start_time=st,
                                   end_time=en, room=r.get("room") or None))
    await db.execute(delete(TimetableSlot).where(TimetableSlot.user_id == user.id))
    db.add_all(slots)
    await db.commit()
    return {"imported": len(slots), "classes": len(classes)}


# --------------------------------------------------------------------------- calendar


class EventIn(BaseModel):
    kind: str = Field(pattern="^(holiday|ramadan|exam|short_day|term|event)$")
    title: str
    start_date: date
    end_date: date
    duration_factor: float = Field(1.0, ge=0.3, le=1.0)


def event_out(e: CalendarEvent) -> dict[str, Any]:
    return {"id": str(e.id), "kind": e.kind, "title": e.title, "start_date": e.start_date.isoformat(),
            "end_date": e.end_date.isoformat(), "duration_factor": e.duration_factor, "global": e.user_id is None}


@router.get("/calendar/events")
async def list_events(user: CurrentUser, db: DB, start: date | None = None, end: date | None = None):
    q = select(CalendarEvent).where((CalendarEvent.user_id == user.id) | (CalendarEvent.user_id.is_(None)))
    if start:
        q = q.where(CalendarEvent.end_date >= start)
    if end:
        q = q.where(CalendarEvent.start_date <= end)
    rows = (await db.execute(q.order_by(CalendarEvent.start_date))).scalars().all()
    return {"items": [event_out(e) for e in rows]}


@router.post("/calendar/events")
async def create_event(data: EventIn, user: CurrentUser, db: DB):
    if data.end_date < data.start_date:
        raise AppError("bad_request", "End date is before start date.", 400)
    e = CalendarEvent(user_id=user.id, **data.model_dump())
    db.add(e)
    await db.commit()
    return event_out(e)


@router.delete("/calendar/events/{event_id}")
async def delete_event(event_id: uuid.UUID, user: CurrentUser, db: DB):
    e = await db.get(CalendarEvent, event_id)
    if e is None or e.user_id != user.id:
        raise NotFound("Event")
    await db.delete(e)
    await db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- planner


@router.get("/planner/day")
async def plan_day(user: CurrentUser, db: DB, day: date | None = None):
    d = day or planner.today_for(user)
    return (await planner.build_days(db, user, [d]))[0]


@router.get("/planner/week")
async def plan_week(user: CurrentUser, db: DB, start: date | None = None):
    days = await planner.week_days(db, user, start or planner.today_for(user))
    return {"days": await planner.build_days(db, user, days)}


class PrepareIn(BaseModel):
    scope: str = Field("today", pattern="^(today|tomorrow|week|date)$")
    day: date | None = None
    with_documents: bool = False


@router.post("/planner/prepare")
async def prepare(data: PrepareIn, user: CurrentUser, db: DB):
    today = planner.today_for(user)
    if data.scope == "today":
        days = [today]
    elif data.scope == "tomorrow":
        days = [await planner.next_working_day(db, user, today)]
    elif data.scope == "date" and data.day:
        days = [data.day]
    else:
        days = await planner.week_days(db, user, today)
    return await planner.prepare(db, user, days, with_documents=data.with_documents)


@router.get("/planner/history")
async def history(user: CurrentUser, db: DB, class_id: uuid.UUID | None = None, days: int = 14):
    return {"items": await planner.history(db, user, class_id=class_id, days=min(days, 120))}


@router.get("/planner/next")
async def next_topics(user: CurrentUser, db: DB):
    classes = (await db.execute(select(ClassSection).where(ClassSection.user_id == user.id))).scalars().all()
    out = []
    for c in classes:
        out.append({"class": class_out(c), "suggestion": await planner.suggest_next_topic(db, user, c)})
    return {"items": out}


# --------------------------------------------------------------------------- curriculum


@router.get("/curricula")
async def curricula(db: DB):
    from app.models import CurriculumFramework

    rows = (await db.execute(select(CurriculumFramework).order_by(CurriculumFramework.name))).scalars().all()
    return {"items": [{"code": r.code, "name": r.name, "country": r.country} for r in rows]}


@router.get("/curricula/{framework}/outcomes")
async def outcomes(framework: str, user: CurrentUser, db: DB, subject: str | None = None, grade: str | None = None,
                   q: str | None = None):
    query = select(LearningOutcome).where(LearningOutcome.framework_code == framework,
                                          (LearningOutcome.owner_id.is_(None)) | (LearningOutcome.owner_id == user.id))
    if subject:
        query = query.where(LearningOutcome.subject.ilike(subject))
    if grade:
        query = query.where(LearningOutcome.grade == grade)
    if q:
        query = query.where(LearningOutcome.text.ilike(f"%{q}%") | LearningOutcome.strand.ilike(f"%{q}%"))
    rows = (await db.execute(query.order_by(LearningOutcome.code).limit(200))).scalars().all()
    return {"items": [{"id": str(o.id), "code": o.code, "subject": o.subject, "grade": o.grade, "strand": o.strand,
                       "text": o.text, "custom": o.owner_id is not None} for o in rows]}


class OutcomeIn(BaseModel):
    framework_code: str
    subject: str
    grade: str
    strand: str | None = None
    code: str
    text: str


@router.post("/curricula/outcomes")
async def add_outcome(data: OutcomeIn, user: CurrentUser, db: DB):
    o = LearningOutcome(owner_id=user.id, **data.model_dump())
    db.add(o)
    await db.commit()
    return {"id": str(o.id)}


@router.get("/curriculum/coverage")
async def coverage(user: CurrentUser, db: DB, class_id: uuid.UUID):
    c = await _owned_class(db, user, class_id)
    tp = await _profile(db, user)
    framework = c.curriculum or tp.curriculum
    outs = (await db.execute(select(LearningOutcome).where(
        LearningOutcome.framework_code == framework, LearningOutcome.grade == c.grade,
        LearningOutcome.subject.ilike(c.subject)).order_by(LearningOutcome.code))).scalars().all()
    courses = (await db.execute(select(Course).where(Course.owner_id == user.id, Course.class_section_id == c.id))
               ).scalars().all()
    status: dict[str, str] = {}
    for course in courses:
        lessons = (await db.execute(select(Lesson.status).where(Lesson.course_id == course.id))).scalars().all()
        state = "taught" if lessons and all(s in ("taught", "reflected") for s in lessons) else (
            "in_progress" if any(s in ("taught", "reflected") for s in lessons) else "planned")
        for code in course.outcome_codes or []:
            status[code] = state
        for o in outs:
            if (o.strand or "").lower() == course.topic.lower() and o.code not in status:
                status[o.code] = state
    items = [{"code": o.code, "strand": o.strand, "text": o.text, "status": status.get(o.code, "not_covered")}
             for o in outs]
    done = sum(1 for i in items if i["status"] == "taught")
    return {"class": class_out(c), "framework": framework, "items": items,
            "summary": {"total": len(items), "taught": done,
                        "in_progress": sum(1 for i in items if i["status"] == "in_progress"),
                        "planned": sum(1 for i in items if i["status"] == "planned")}}
