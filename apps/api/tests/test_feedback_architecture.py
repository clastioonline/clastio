"""Teacher feedback isolation and bundle retries against real PostgreSQL."""
import uuid

import pytest
from sqlalchemy import func, select

from app.core.db import get_sessionmaker
from app.core.errors import NotFound
from app.jobs.queue import JobContext
from app.models import Course, Document, Lesson, Project, Slide, SlideFeedback, TeacherMemory, User
from app.services.bundles import complete_bundle
from app.services.feedback import accept


async def sample():
    async with get_sessionmaker()() as db:
        user = User(email=f"feedback-{uuid.uuid4()}@example.com", name="Feedback Teacher")
        other = User(email=f"feedback-{uuid.uuid4()}@example.com", name="Other Teacher")
        db.add_all([user, other])
        await db.flush()
        project = Project(owner_id=user.id, title="Addition")
        db.add(project)
        await db.flush()
        course = Course(owner_id=user.id, project_id=project.id, topic="Addition", subject="Maths", grade="2",
                        curriculum="british", num_lectures=1, slides_per_lecture=6)
        db.add(course)
        await db.flush()
        lesson = Lesson(owner_id=user.id, course_id=course.id, number=1, title="Addition")
        db.add(lesson)
        await db.flush()
        slide = Slide(lesson_id=lesson.id, number=1, version=1,
                      spec={"number": 1, "title": "Addition", "layout": "concept", "bullets": []})
        db.add(slide)
        await db.commit()
        return user.id, other.id, lesson.id, slide.id


async def test_acceptance_is_idempotent_and_owner_scoped(database):
    owner, other, lesson, slide = await sample()
    async with get_sessionmaker()() as db:
        user = await db.get(User, owner)
        await accept(db, user, lesson, 1)
        await db.commit()
        await accept(db, user, lesson, 1)
        await db.commit()
        count = (await db.execute(select(func.count()).select_from(SlideFeedback).where(SlideFeedback.slide_id == slide))).scalar_one()
        assert count == 1
        memories = (await db.execute(select(TeacherMemory).where(TeacherMemory.user_id == owner,
                                                               TeacherMemory.kind == "accepted_slide"))).scalars().all()
        assert len(memories) == 1
        assert memories[0].meta["slide"]["title"] == "Addition"
        assert memories[0].embedding is not None
        stranger = await db.get(User, other)
        with pytest.raises(NotFound):
            await accept(db, stranger, lesson, 1)


async def test_ready_bundle_documents_are_reused_on_retry(database):
    owner, _, lesson_id, _ = await sample()
    job_id = uuid.uuid4()
    async with get_sessionmaker()() as db:
        lesson = await db.get(Lesson, lesson_id)
        for kind in ("lesson_plan", "worksheet", "quiz"):
            db.add(Document(id=uuid.uuid5(job_id, kind), owner_id=owner, lesson_id=lesson_id,
                            course_id=lesson.course_id, kind=kind, title=kind, status="ready"))
        await db.commit()
    ctx = JobContext(job_id=job_id, owner_id=owner, payload={})
    first = await complete_bundle(ctx, lesson_id, owner)
    second = await complete_bundle(ctx, lesson_id, owner)
    assert first == second
    async with get_sessionmaker()() as db:
        count = (await db.execute(select(func.count()).select_from(Document).where(Document.lesson_id == lesson_id))).scalar_one()
        assert count == 3


async def test_complete_bundle_through_http(client, teacher):
    headers = teacher["headers"]
    response = await client.post("/api/v1/courses", headers=headers, json={
        "topic": "Addition", "subject": "Mathematics", "grade": "2", "num_lectures": 1,
        "slides_per_lecture": 6, "auto_generate": False})
    assert response.status_code == 200, response.text
    course_id = response.json()["course"]["id"]
    response = await client.post(f"/api/v1/courses/{course_id}/generate", headers=headers,
                                 json={"lessons": [1], "bundle": True})
    assert response.status_code == 202, response.text
    job_id = uuid.UUID(response.json()["job_ids"][0])
    from app.models import GenerationJob
    async with get_sessionmaker()() as db:
        job = await db.get(GenerationJob, job_id)
        assert job.status == "succeeded", job.error
        docs = (await db.execute(select(Document).where(Document.course_id == uuid.UUID(course_id)))).scalars().all()
        assert {doc.kind for doc in docs} == {"lesson_plan", "worksheet", "quiz"}
        assert all(doc.status == "ready" and "docx" in doc.files for doc in docs)
        worksheet = next(doc for doc in docs if doc.kind == "worksheet")
        assert [section["title"] for section in worksheet.content["data"]["sections"]] == ["Support", "Core", "Extension"]
        quiz = next(doc for doc in docs if doc.kind == "quiz")
        assert {"csv", "gift"} <= set(quiz.files)


async def test_voice_course_retry_reuses_course(client, teacher):
    from app.services.courses import create_course
    async with get_sessionmaker()() as db:
        user = await db.get(User, uuid.UUID(teacher["id"]))
        data = {"topic": "Addition", "subject": "Mathematics", "grade": "2", "num_lectures": 1,
                "slides_per_lecture": 6, "auto_generate": False, "request_key": "wamid.retry-example"}
        first, first_job = await create_course(db, user, data)
        second, second_job = await create_course(db, user, data)
        assert first.id == second.id
        assert first_job == second_job
