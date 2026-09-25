"""Timetable-aware planning: today / tomorrow / week, next topic, and the post-lesson reflection loop."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.jobs.queue import enqueue, run_inline_if_configured
from app.models import (
    CalendarEvent,
    ClassSection,
    Course,
    Document,
    LearningOutcome,
    Lesson,
    LessonReflection,
    Slide,
    TeacherProfile,
    TimetableSlot,
    User,
)
from app.services import memory as memory_svc
from app.services import usage
from app.services.courses import class_active_course, get_owned

PENDING = ("planned", "generating", "generated", "failed")
DONE = ("taught", "reflected")


def today_for(user: User) -> date:
    return datetime.now(ZoneInfo(user.timezone or "Asia/Dubai")).date()


async def calendar_for(db: AsyncSession, user: User, day: date) -> list[CalendarEvent]:
    return list((await db.execute(select(CalendarEvent).where(
        or_(CalendarEvent.user_id == user.id, and_(CalendarEvent.user_id.is_(None), CalendarEvent.org_id.is_(None)),
            and_(CalendarEvent.org_id.is_not(None), CalendarEvent.org_id == user.org_id)),
        CalendarEvent.start_date <= day, CalendarEvent.end_date >= day))).scalars().all())


async def _slots(db: AsyncSession, user: User, weekday: int) -> list[TimetableSlot]:
    return list((await db.execute(select(TimetableSlot).where(
        TimetableSlot.user_id == user.id, TimetableSlot.day_of_week == weekday).order_by(TimetableSlot.start_time))
    ).scalars().all())


async def _pending_lessons(db: AsyncSession, course: Course) -> list[Lesson]:
    return list((await db.execute(select(Lesson).where(Lesson.course_id == course.id, Lesson.status.in_(PENDING))
                                  .order_by(Lesson.number))).scalars().all())


async def _materials(db: AsyncSession, lesson: Lesson) -> dict[str, Any]:
    docs = (await db.execute(select(Document.kind, Document.status, Document.id).where(
        Document.lesson_id == lesson.id))).all()
    slides = (await db.execute(select(Slide.id).where(Slide.lesson_id == lesson.id))).all()
    kinds = {k: {"status": s, "id": str(i)} for k, s, i in docs}
    return {"slides": len(slides), "pptx": bool(lesson.pptx_key), "lesson_plan": bool(lesson.plan),
            "documents": kinds}


async def build_days(db: AsyncSession, user: User, days: list[date]) -> list[dict[str, Any]]:
    """Allocate upcoming lessons to timetable slots across the given days (in order)."""
    allocated: set[uuid.UUID] = set()
    out = []
    course_cache: dict[uuid.UUID, Course | None] = {}
    queue_cache: dict[uuid.UUID, list[Lesson]] = {}
    for day in days:
        events = await calendar_for(db, user, day)
        holiday = next((e for e in events if e.kind == "holiday"), None)
        factor = min([e.duration_factor for e in events if e.kind in ("ramadan", "short_day")] or [1.0])
        day_out: dict[str, Any] = {"date": day.isoformat(), "weekday": day.strftime("%A"),
                                   "events": [{"kind": e.kind, "title": e.title} for e in events],
                                   "holiday": holiday.title if holiday else None, "duration_factor": factor,
                                   "classes": []}
        if holiday:
            out.append(day_out)
            continue
        for slot in await _slots(db, user, day.weekday()):
            cs = await db.get(ClassSection, slot.class_section_id)
            if cs is None:
                continue
            if cs.id not in course_cache:
                course_cache[cs.id] = await class_active_course(db, cs.id)
            course = course_cache[cs.id]
            minutes = int((datetime.combine(day, slot.end_time) - datetime.combine(day, slot.start_time))
                          .total_seconds() // 60)
            item: dict[str, Any] = {
                "slot_id": str(slot.id), "start": slot.start_time.strftime("%H:%M"),
                "end": slot.end_time.strftime("%H:%M"), "minutes": int(minutes * factor), "room": slot.room,
                "class": {"id": str(cs.id), "name": cs.name, "grade": cs.grade, "subject": cs.subject,
                          "color": cs.color},
                "course": None, "lesson": None, "suggestion": None}
            if course is None:
                item["suggestion"] = await suggest_next_topic(db, user, cs)
            else:
                item["course"] = {"id": str(course.id), "topic": course.topic, "project_id": str(course.project_id),
                                  "num_lectures": course.num_lectures}
                if course.id not in queue_cache:
                    queue_cache[course.id] = await _pending_lessons(db, course)
                fixed = next((les for les in queue_cache[course.id] if les.scheduled_date == day
                              and les.id not in allocated), None)
                lesson = fixed or next((les for les in queue_cache[course.id] if les.id not in allocated and
                                        (les.scheduled_date is None or les.scheduled_date <= day)), None)
                if lesson:
                    allocated.add(lesson.id)
                    item["lesson"] = {"id": str(lesson.id), "number": lesson.number, "title": lesson.title,
                                      "status": lesson.status, "carry_over": lesson.carry_over or None,
                                      "materials": await _materials(db, lesson)}
                else:
                    item["suggestion"] = await suggest_next_topic(db, user, cs, finished_course=course)
            day_out["classes"].append(item)
        out.append(day_out)
    return out


async def working_days(db: AsyncSession, user: User) -> list[int]:
    tp = (await db.execute(select(TeacherProfile).where(TeacherProfile.user_id == user.id))).scalars().first()
    return list(tp.working_days) if tp and tp.working_days else [0, 1, 2, 3, 4]


async def next_working_day(db: AsyncSession, user: User, start: date) -> date:
    wd = await working_days(db, user)
    d = start + timedelta(days=1)
    for _ in range(14):
        if d.weekday() in wd and not any(e.kind == "holiday" for e in await calendar_for(db, user, d)):
            return d
        d += timedelta(days=1)
    return start + timedelta(days=1)


async def week_days(db: AsyncSession, user: User, start: date) -> list[date]:
    wd = await working_days(db, user)
    monday = start - timedelta(days=start.weekday())
    return [monday + timedelta(days=i) for i in range(7) if (monday + timedelta(days=i)).weekday() in wd]


async def prepare(db: AsyncSession, user: User, days: list[date], *, with_documents: bool = False
                  ) -> dict[str, Any]:
    """Generate every missing lesson (and optionally quiz + homework) for the given days."""
    plan = await build_days(db, user, days)
    lesson_ids: list[tuple[uuid.UUID, int, str]] = []
    for day in plan:
        for item in day["classes"]:
            les = item.get("lesson")
            if les:
                lesson = await db.get(Lesson, uuid.UUID(les["id"]))
                if lesson.scheduled_date is None:
                    lesson.scheduled_date = date.fromisoformat(day["date"])
                if les["status"] in ("planned", "failed"):
                    lesson_ids.append((lesson.id, item["minutes"], day["date"]))
    job_ids = []
    if lesson_ids:
        slides_total = 0
        for lid, _, _ in lesson_ids:
            lesson = await db.get(Lesson, lid)
            course = await db.get(Course, lesson.course_id)
            slides_total += course.slides_per_lecture
        await usage.check(db, user, "credits", await usage.credit_cost("slide", slides_total), jobs=len(lesson_ids))
        for lid, minutes, day_s in lesson_ids:
            lesson = await db.get(Lesson, lid)
            course = await db.get(Course, lesson.course_id)
            instr = None
            if minutes and minutes < course.lecture_minutes:
                instr = (f"This lesson runs {minutes} minutes on {day_s} (shortened school day), so keep it "
                         f"tight: fewer, focused slides and a shorter activity.")
            lesson.status = "generating"
            job = await enqueue(db, "lesson_generation", {"lesson_id": str(lid), "instructions": instr},
                                owner_id=user.id, dedupe=True,
                                credits_reserved=await usage.credit_cost("slide", course.slides_per_lecture))
            job_ids.append(job.id)
    await db.commit()
    await run_inline_if_configured(job_ids)
    doc_jobs = []
    if with_documents:
        from app.services.documents import create_document

        for lid, _, _ in lesson_ids:
            for kind in ("quiz", "homework"):
                try:
                    _, jid = await create_document(db, user, {"kind": kind, "lesson_id": lid, "num_questions":
                                                              5 if kind == "quiz" else 4})
                    doc_jobs.append(jid)
                except AppError:
                    break
    return {"days": plan, "jobs": [str(j) for j in job_ids + doc_jobs], "lessons_queued": len(lesson_ids)}


async def suggest_next_topic(db: AsyncSession, user: User, cs: ClassSection,
                             finished_course: Course | None = None) -> dict[str, Any]:
    """Next curriculum outcome not yet covered for this class's grade/subject."""
    tp = (await db.execute(select(TeacherProfile).where(TeacherProfile.user_id == user.id))).scalars().first()
    framework = (cs.curriculum or (tp.curriculum if tp else "british"))
    covered_codes: set[str] = set()
    for (codes,) in (await db.execute(select(Course.outcome_codes).where(Course.owner_id == user.id,
                                                                         Course.class_section_id == cs.id))).all():
        covered_codes.update(codes or [])
    covered_topics = {t.lower() for (t,) in (await db.execute(select(Course.topic).where(
        Course.owner_id == user.id, Course.class_section_id == cs.id))).all()}
    outcomes = (await db.execute(select(LearningOutcome).where(
        LearningOutcome.framework_code == framework, LearningOutcome.grade == cs.grade,
        LearningOutcome.subject.ilike(cs.subject)).order_by(LearningOutcome.code))).scalars().all()
    for o in outcomes:
        if o.code not in covered_codes and (o.strand or "").lower() not in covered_topics:
            return {"topic": o.strand or o.text[:60], "outcome": {"code": o.code, "text": o.text},
                    "reason": f"Next uncovered {framework.upper()} outcome for Grade {cs.grade} {cs.subject}"}
    msg = f"'{finished_course.topic}' is complete." if finished_course else "No course is planned for this class."
    return {"topic": None, "outcome": None, "reason": msg + " Create a new course to continue."}


# --------------------------------------------------------------------------- reflections


async def record_reflection(db: AsyncSession, user: User, lesson_id: uuid.UUID, outcome: str,
                            note: str | None = None, covered_until_slide: int | None = None,
                            channel: str = "web") -> dict[str, Any]:
    if outcome not in ("went_well", "ran_out_of_time", "struggled", "skipped"):
        raise AppError("bad_request", "Unknown reflection outcome", 400)
    lesson = await get_owned(db, Lesson, lesson_id, user)
    course = await db.get(Course, lesson.course_id)
    db.add(LessonReflection(lesson_id=lesson.id, owner_id=user.id, outcome=outcome, note=note,
                            covered_until_slide=covered_until_slide, channel=channel))
    nxt = (await db.execute(select(Lesson).where(Lesson.course_id == course.id, Lesson.number == lesson.number + 1))
           ).scalars().first()
    effects: list[str] = []
    cs = await db.get(ClassSection, course.class_section_id) if course.class_section_id else None
    label = f"{cs.name} " if cs else ""
    if outcome == "skipped":
        lesson.status = "generated" if lesson.pptx_key else "planned"
        lesson.scheduled_date = None
        effects.append("Lesson moved back to the top of the queue for this class.")
    else:
        lesson.status = "reflected"
        lesson.taught_at = datetime.now(ZoneInfo(user.timezone or "Asia/Dubai"))
    if outcome == "ran_out_of_time" and nxt is not None:
        slides = (await db.execute(select(Slide).where(Slide.lesson_id == lesson.id).order_by(Slide.number))
                  ).scalars().all()
        start = (covered_until_slide or max(1, len(slides) // 2)) + 1
        remaining = [s.spec.get("title") for s in slides if s.number >= start and
                     s.spec.get("layout") not in ("cover", "homework")]
        nxt.carry_over = {"text": f"Last lesson ran out of time. Begin by finishing: {', '.join(remaining[:5])}.",
                          "from_lesson": lesson.number, "kind": "carry_over"}
        effects.append(f"Unfinished part ({len(remaining)} slides) carried into lesson {nxt.number}.")
        if cs:
            recent = (await db.execute(select(LessonReflection).where(
                LessonReflection.owner_id == user.id, LessonReflection.outcome == "ran_out_of_time")
                .order_by(LessonReflection.created_at.desc()).limit(3))).scalars().all()
            if len(recent) >= 2 and cs.pace == "standard":  # repeated signal, not a one-off
                cs.pace = "slower"
                effects.append(f"{cs.name} pace set to 'slower' — future lessons will be lighter.")
    if outcome == "struggled":
        text = note or f"Students found '{lesson.title}' difficult"
        await memory_svc.add_memory(db, user.id, "misconception", f"{label}{course.topic}: {text}",
                                    class_section_id=course.class_section_id, lesson_id=lesson.id)
        if nxt is not None:
            nxt.carry_over = {"text": f"Students struggled last lesson ({text}). Start with a 5-minute remedial "
                                      f"recap using a different explanation and a worked example.",
                              "from_lesson": lesson.number, "kind": "remedial"}
            effects.append(f"A remedial starter will open lesson {nxt.number}.")
    await memory_svc.add_memory(db, user.id, "reflection",
                                f"{label}lesson '{lesson.title}' ({course.topic}): {outcome.replace('_', ' ')}"
                                + (f" — {note}" if note else ""),
                                class_section_id=course.class_section_id, lesson_id=lesson.id, embed=False)
    regenerate_suggested = bool(nxt and nxt.pptx_key and outcome in ("ran_out_of_time", "struggled"))
    await db.commit()
    return {"lesson_id": str(lesson.id), "status": lesson.status, "effects": effects,
            "next_lesson_id": str(nxt.id) if nxt else None, "regenerate_next_suggested": regenerate_suggested}


async def history(db: AsyncSession, user: User, *, class_id: uuid.UUID | None = None, days: int = 7
                  ) -> list[dict[str, Any]]:
    since = today_for(user) - timedelta(days=days)
    q = select(Lesson, Course).join(Course, Course.id == Lesson.course_id).where(
        Lesson.owner_id == user.id,
        or_(Lesson.scheduled_date >= since, Lesson.taught_at >= datetime.combine(since, datetime.min.time())))
    if class_id:
        q = q.where(Course.class_section_id == class_id)
    rows = (await db.execute(q.order_by(Lesson.scheduled_date.desc().nullslast()))).all()
    out = []
    for lesson, course in rows:
        cs = await db.get(ClassSection, course.class_section_id) if course.class_section_id else None
        out.append({"date": (lesson.taught_at.date().isoformat() if lesson.taught_at else
                             lesson.scheduled_date.isoformat() if lesson.scheduled_date else None),
                    "class": cs.name if cs else None, "topic": course.topic, "lesson": lesson.number,
                    "title": lesson.title, "status": lesson.status, "lesson_id": str(lesson.id)})
    return out
