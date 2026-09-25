"""Seed data: plans, built-in templates, curriculum frameworks + sample outcomes, calendar, demo accounts.

    python -m app.seed            # plans, templates, frameworks, outcomes, calendar
    python -m app.seed --demo     # + admin and demo teacher with classes and a timetable

The outcome library below is an ILLUSTRATIVE starter set (topic-level strands with our own codes) so planning
and coverage features work out of the box. Import the official framework documents for production use.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import date, time

from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.core.security import hash_password
from app.models import (
    CalendarEvent,
    ClassSection,
    CurriculumFramework,
    LearningOutcome,
    TeacherPreference,
    TeacherProfile,
    TimetableSlot,
    User,
)
from app.services.billing import seed_plans
from app.services.styles import ensure_builtin_templates

FRAMEWORKS = [
    ("british", "British — England National Curriculum / IGCSE", "GB"),
    ("cbse", "CBSE (NCERT) — India", "IN"),
    ("icse", "ICSE — India", "IN"),
    ("american", "American — Common Core / NGSS", "US"),
    ("ib", "International Baccalaureate", None),
    ("moe", "UAE Ministry of Education", "AE"),
    ("uae_ai", "UAE MoE Artificial Intelligence Curriculum (KG–12)", "AE"),
]

# (framework, subject, grade, strand, text)
OUTCOMES: list[tuple[str, str, str, str, str]] = [
    ("british", "Science", "8", "Photosynthesis", "Describe photosynthesis, its reactants and products, and the role of chlorophyll"),
    ("british", "Science", "8", "Respiration", "Compare aerobic and anaerobic respiration in plants and animals"),
    ("british", "Science", "8", "Particle model", "Explain states of matter and changes of state using the particle model"),
    ("british", "Science", "8", "Atoms, elements and compounds", "Distinguish between elements, compounds and mixtures"),
    ("british", "Science", "8", "Forces and motion", "Describe balanced and unbalanced forces and their effect on motion"),
    ("british", "Science", "8", "Energy transfers", "Describe energy stores and transfers, including efficiency"),
    ("british", "Science", "8", "Electricity", "Explain current, voltage and resistance in series and parallel circuits"),
    ("british", "Science", "8", "Ecosystems", "Describe food webs, interdependence and the effects of human activity"),
    ("british", "Science", "7", "Cells", "Describe plant and animal cell structures and the function of organelles"),
    ("british", "Science", "7", "The water cycle", "Explain evaporation, condensation and precipitation in the water cycle"),
    ("british", "Mathematics", "6", "Fractions", "Add and subtract fractions with different denominators"),
    ("british", "Mathematics", "6", "Ratio and proportion", "Solve problems involving ratio and proportion"),
    ("british", "Mathematics", "6", "Algebra basics", "Use simple formulae and generate sequences"),
    ("british", "Mathematics", "6", "Angles", "Measure and calculate angles in triangles and on straight lines"),
    ("cbse", "Science", "8", "Microorganisms", "Identify useful and harmful microorganisms and their roles"),
    ("cbse", "Science", "8", "Force and pressure", "Explain force, pressure and their everyday applications"),
    ("cbse", "Science", "8", "Friction", "Describe friction, factors affecting it, and ways to increase or reduce it"),
    ("cbse", "Science", "8", "Sound", "Explain how sound is produced, travels and is heard"),
    ("cbse", "Science", "8", "Light", "Describe reflection of light and the structure of the human eye"),
    ("cbse", "Science", "8", "Conservation of plants and animals", "Explain deforestation, biodiversity and conservation"),
    ("cbse", "Mathematics", "8", "Rational numbers", "Represent and operate on rational numbers"),
    ("cbse", "Mathematics", "8", "Linear equations", "Solve linear equations in one variable"),
    ("american", "Science", "8", "Photosynthesis and energy flow", "Construct an explanation for the role of photosynthesis in the cycling of matter"),
    ("american", "Science", "8", "Forces and interactions", "Apply Newton's third law to a problem involving colliding objects"),
    ("american", "Mathematics", "6", "Ratios and rates", "Understand ratio concepts and use ratio reasoning"),
    ("uae_ai", "Artificial Intelligence", "8", "Foundational AI concepts", "Explain what AI is and how it differs from traditional programs"),
    ("uae_ai", "Artificial Intelligence", "8", "Data and algorithms", "Describe how data trains algorithms and how bias can enter"),
    ("uae_ai", "Artificial Intelligence", "8", "Software applications", "Identify AI applications in daily life and in the UAE"),
    ("uae_ai", "Artificial Intelligence", "8", "Ethical awareness", "Evaluate ethical questions about privacy, fairness and responsible AI use"),
    ("uae_ai", "Artificial Intelligence", "8", "Real-world applications", "Analyse how AI is used in healthcare, transport and government services"),
    ("uae_ai", "Artificial Intelligence", "8", "Innovation and project design", "Design a simple AI-supported solution to a local problem"),
    ("uae_ai", "Artificial Intelligence", "8", "Policies and community engagement", "Discuss national AI strategy and community impact"),
]

# Global calendar (visible to everyone). Lunar dates are estimates - schools confirm the official dates.
CALENDAR = [
    ("holiday", "Commemoration Day", date(2026, 12, 1), date(2026, 12, 1), 1.0),
    ("holiday", "UAE National Day", date(2026, 12, 2), date(2026, 12, 3), 1.0),
    ("ramadan", "Ramadan timings (estimated — confirm with your school)", date(2027, 2, 8), date(2027, 3, 8), 0.75),
    ("holiday", "Eid al-Fitr (estimated)", date(2027, 3, 9), date(2027, 3, 11), 1.0),
]


async def seed_core() -> None:
    async with get_sessionmaker()() as db:
        await seed_plans(db)
        for code, name, country in FRAMEWORKS:
            if await db.get(CurriculumFramework, code) is None:
                db.add(CurriculumFramework(code=code, name=name, country=country))
        await db.flush()
        existing = {(o.framework_code, o.code) for o in (await db.execute(select(LearningOutcome))).scalars().all()}
        counters: dict[tuple, int] = {}
        for fw, subject, grade, strand, text in OUTCOMES:
            key = (fw, subject, grade)
            counters[key] = counters.get(key, 0) + 1
            code = f"{fw.upper()}-{subject[:3].upper()}-{grade}-{counters[key]:02d}"
            if (fw, code) not in existing:
                db.add(LearningOutcome(framework_code=fw, subject=subject, grade=grade, strand=strand, code=code,
                                       text=text))
        for kind, title, start, end, factor in CALENDAR:
            dup = (await db.execute(select(CalendarEvent).where(CalendarEvent.user_id.is_(None),
                                                                CalendarEvent.title == title))).scalars().first()
            if not dup:
                db.add(CalendarEvent(kind=kind, title=title, start_date=start, end_date=end, duration_factor=factor))
        await ensure_builtin_templates(db)
        await db.commit()
    await embed_outcomes()


async def embed_outcomes() -> None:
    from app.ai.service import get_ai

    async with get_sessionmaker()() as db:
        rows = (await db.execute(select(LearningOutcome).where(LearningOutcome.embedding.is_(None)))).scalars().all()
        if rows:
            vecs = await get_ai().embed([f"{r.subject} grade {r.grade} {r.strand}: {r.text}" for r in rows])
            for r, v in zip(rows, vecs, strict=False):
                r.embedding = v
            await db.commit()


async def seed_demo() -> dict[str, str]:
    async with get_sessionmaker()() as db:
        admin = (await db.execute(select(User).where(User.email == "admin@example.com"))).scalars().first()
        if admin is None:
            db.add(User(email="admin@example.com", name="Platform Admin", role="admin",
                        password_hash=hash_password("admin-demo-123"), email_verified=True))
        teacher = (await db.execute(select(User).where(User.email == "sara@example.com"))).scalars().first()
        if teacher is None:
            teacher = User(id=uuid.uuid4(), email="sara@example.com", name="Sara Ahmed",
                           password_hash=hash_password("teacher-demo-123"), email_verified=True)
            db.add(teacher)
            await db.flush()
            db.add(TeacherProfile(user_id=teacher.id, country="AE", region="Dubai", school_name="Demo Academy",
                                  curriculum="british", subjects=["Science"], grades=["7", "8"],
                                  class_duration_minutes=45, classes_per_day=4, onboarding_completed=True,
                                  teaching_style="Visual, lots of questioning, real-world UAE examples"))
            for key, value in (("language_level", "simple English"), ("real_world_examples", True),
                               ("recap_first", True), ("homework_last", True), ("quiz_length", 5),
                               ("visual_explanations", True)):
                db.add(TeacherPreference(user_id=teacher.id, key=key, value=value))
            classes = []
            for name, grade, color in (("8A", "8", "#0F766E"), ("8B", "8", "#2563EB"), ("7C", "7", "#9333EA")):
                cs = ClassSection(user_id=teacher.id, name=name, grade=grade, subject="Science", curriculum="british",
                                  eal_percent=35, color=color)
                db.add(cs)
                classes.append(cs)
            await db.flush()
            slots = [(0, 0, "07:45"), (0, 2, "09:30"), (1, 1, "08:30"), (1, 0, "10:15"), (2, 2, "07:45"),
                     (2, 0, "11:00"), (3, 1, "09:30"), (3, 2, "12:00"), (4, 0, "08:30")]
            for day, ci, start in slots:
                h, m = map(int, start.split(":"))
                db.add(TimetableSlot(user_id=teacher.id, class_section_id=classes[ci].id, day_of_week=day,
                                     start_time=time(h, m), end_time=time(h + (m + 45) // 60, (m + 45) % 60)))
        await db.commit()
        from app.services.billing import set_manual_plan
        from app.services.usage import active_subscription

        if await active_subscription(db, teacher.id) is None:
            await set_manual_plan(db, teacher.id, "assistant", months=12)
    return {"admin": "admin@example.com / admin-demo-123", "teacher": "sara@example.com / teacher-demo-123"}


async def main(demo: bool) -> None:
    await seed_core()
    if demo:
        creds = await seed_demo()
        print("Demo accounts:", creds)
    print("Seed complete.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    asyncio.run(main(ap.parse_args().demo))
