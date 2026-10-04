from __future__ import annotations

import io
import uuid

import pytest
from pptx import Presentation
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.core.errors import NotFound
from app.engine.template.builder import BUILTIN_STYLES, build_builtin
from app.generation.quality import ContentQualityError
from app.jobs.queue import HANDLERS, enqueue, run_job
from app.models import GenerationJob, Lesson, Template
from app.services.courses import resolve_template


async def test_bad_content_fails_once_and_releases_teacher_credit_reservation(teacher, monkeypatch):
    async def invalid(_context):
        raise ContentQualityError("The assessment did not pass its answer-key checks.")

    monkeypatch.setitem(HANDLERS, "quality_rejection_test", invalid)
    async with get_sessionmaker()() as db:
        job = await enqueue(db, "quality_rejection_test", {}, owner_id=uuid.UUID(teacher["id"]), credits_reserved=10)
        await db.commit()
        job_id = job.id
    await run_job(job_id)
    async with get_sessionmaker()() as db:
        job = await db.get(GenerationJob, job_id)
        assert job.status == "failed"
        assert job.attempts == 1
        assert job.credits_reserved == 0


async def test_generated_ppt_contains_requested_slides_and_records_review_boundary(client, teacher):
    response = await client.post("/api/v1/courses", headers=teacher["headers"], json={
        "topic": "Addition", "grade": "2", "subject": "Mathematics", "curriculum": "british",
        "num_lectures": 1, "slides_per_lecture": 20, "lecture_minutes": 40, "auto_generate": True,
    })
    assert response.status_code == 200, response.text
    course_id = uuid.UUID(response.json()["course"]["id"])
    async with get_sessionmaker()() as db:
        lesson = (await db.execute(select(Lesson).where(Lesson.course_id == course_id))).scalar_one()
        assert lesson.status == "generated", lesson.error
        assert lesson.qc_report["content_quality"] == {"status": "structural_checks_passed", "reference_count": 0,
                                                       "fact_check_status": "teacher_review_required"}
        assert sum(phase["minutes"] for phase in lesson.plan["phases"]) == 40
        from app.core.storage import get_storage

        data = await get_storage().get(lesson.pptx_key)
        assert len(Presentation(io.BytesIO(data)).slides) == 20


async def test_explicit_foreign_template_is_not_replaced_by_a_generic_fallback(client, teacher):
    from tests.conftest import make_user

    other = await make_user(client)
    async with get_sessionmaker()() as db:
        template = Template(owner_id=uuid.UUID(other["id"]), name="Private school design", is_shared=True,
                            org_id=None, mode="library", base_storage_key="unused",
                            spec=build_builtin(next(iter(BUILTIN_STYLES)))[1])
        db.add(template)
        await db.commit()
        with pytest.raises(NotFound):
            await resolve_template(db, uuid.UUID(teacher["id"]), template.id)
