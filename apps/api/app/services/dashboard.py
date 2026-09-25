"""Data for the teacher dashboard: headline numbers, this week's activity, the next class, upcoming lessons,
classes, curriculum coverage and the getting-started checklist."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ClassSection,
    Course,
    Document,
    GenerationJob,
    Lesson,
    StyleProfile,
    TimetableSlot,
    User,
    WhatsAppContact,
)
from app.services import planner
from app.services.courses import class_active_course

READY = ("generated",)
TAUGHT = ("taught", "reflected")
BUILDING = ("generating",)
PENDING = ("planned", "failed")


async def _count(db: AsyncSession, *where) -> int:
    return int((await db.execute(select(func.count()).select_from(Lesson).where(*where))).scalar_one())


async def teacher_dashboard(db: AsyncSession, user: User) -> dict[str, Any]:
    tz = ZoneInfo(user.timezone or "Asia/Dubai")
    now = datetime.now(tz)
    today = now.date()
    month_start = datetime(today.year, today.month, 1, tzinfo=tz)
    mine = Lesson.owner_id == user.id

    kpis = {}
    for key, statuses in (("ready", READY), ("taught", TAUGHT), ("building", BUILDING), ("pending", PENDING)):
        kpis[key] = await _count(db, mine, Lesson.status.in_(statuses))
    kpis["total"] = await _count(db, mine)
    kpis["new_this_month"] = await _count(db, mine, Lesson.created_at >= month_start)

    # Lessons prepared per day this week (Monday first), from finished generation jobs.
    week_start = today - timedelta(days=today.weekday())
    day = cast(func.timezone(str(tz), GenerationJob.completed_at), Date)
    rows = (await db.execute(select(day, func.count()).where(
        GenerationJob.owner_id == user.id, GenerationJob.type == "lesson_generation",
        GenerationJob.status == "succeeded",
        GenerationJob.completed_at >= datetime.combine(week_start, datetime.min.time(), tz).astimezone(UTC))
        .group_by(day))).all()
    per_day = {d: c for d, c in rows}
    week = [{"date": (week_start + timedelta(days=i)).isoformat(),
             "label": (week_start + timedelta(days=i)).strftime("%a"),
             "value": int(per_day.get(week_start + timedelta(days=i), 0)),
             "future": week_start + timedelta(days=i) > today, "today": week_start + timedelta(days=i) == today}
            for i in range(7)]

    # Next class: the first slot today that hasn't ended, else the first on the next working day.
    next_class = None
    for d in [today, await planner.next_working_day(db, user, today)]:
        days = await planner.build_days(db, user, [d])
        for c in days[0]["classes"] if days else []:
            if d > today or c["end"] >= now.strftime("%H:%M"):
                next_class = {**c, "date": d.isoformat(), "is_today": d == today}
                break
        if next_class:
            break

    upcoming_rows = (await db.execute(
        select(Lesson, Course).join(Course, Course.id == Lesson.course_id)
        .where(mine, Lesson.status.in_(READY + BUILDING + PENDING))
        .order_by(Lesson.scheduled_date.asc().nullslast(), Course.created_at.desc(), Lesson.number)
        .limit(5))).all()
    upcoming = [{"id": str(les.id), "title": les.title, "number": les.number, "topic": c.topic,
                 "subject": c.subject, "grade": c.grade, "status": les.status,
                 "scheduled_date": les.scheduled_date.isoformat() if les.scheduled_date else None,
                 "project_id": str(c.project_id)} for les, c in upcoming_rows]

    classes = []
    for cs in (await db.execute(select(ClassSection).where(ClassSection.user_id == user.id)
                                .order_by(ClassSection.name))).scalars().all()[:6]:
        course = await class_active_course(db, cs.id)
        nxt = None
        if course:
            nxt = (await db.execute(select(Lesson).where(Lesson.course_id == course.id,
                                                         Lesson.status.notin_(TAUGHT))
                                    .order_by(Lesson.number))).scalars().first()
        state = "pending" if nxt is None else ("ready" if nxt.status in READY else
                                               "in_progress" if nxt.status in BUILDING else "pending")
        classes.append({"id": str(cs.id), "name": cs.name, "grade": cs.grade, "subject": cs.subject,
                        "color": cs.color, "topic": course.topic if course else None,
                        "next_lesson": {"id": str(nxt.id), "number": nxt.number, "title": nxt.title} if nxt else None,
                        "status": state})

    coverage = {"total": 0, "taught": 0, "in_progress": 0, "planned": 0}
    if classes:
        from app.api.routes.teacher import coverage as class_coverage

        for c in classes:
            try:
                s = (await class_coverage(user, db, uuid.UUID(c["id"])))["summary"]
            except Exception:  # a class without a matching framework has no outcomes
                continue
            for k in coverage:
                coverage[k] += int(s.get(k, 0))

    has = {
        "template": (await db.execute(select(StyleProfile.id).where(StyleProfile.owner_id == user.id).limit(1))
                     ).first() is not None,
        "course": (await db.execute(select(Course.id).where(Course.owner_id == user.id).limit(1))).first() is not None,
        "class": bool(classes),
        "timetable": (await db.execute(select(TimetableSlot.id).where(TimetableSlot.user_id == user.id).limit(1))
                      ).first() is not None,
        "document": (await db.execute(select(Document.id).where(Document.owner_id == user.id).limit(1))
                     ).first() is not None,
        "whatsapp": (await db.execute(select(WhatsAppContact.id).where(WhatsAppContact.user_id == user.id,
                                                                       WhatsAppContact.verified.is_(True)).limit(1))
                     ).first() is not None,
    }
    return {"kpis": kpis, "week": week, "next_class": next_class, "upcoming": upcoming, "classes": classes,
            "coverage": coverage, "checklist": has}
