import io
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from PIL import Image

from app.core.errors import AppError
from app.services import courses, styles


@pytest.fixture
def env(monkeypatch):
    user = SimpleNamespace(id=uuid.uuid4())
    course = SimpleNamespace(id=uuid.uuid4(), plan={"lectures": [1]}, slides_per_lecture=10,
                             project_id=uuid.uuid4(), status="planned")
    lessons = [SimpleNamespace(id=uuid.uuid4(), number=n, status="planned", pptx_key=None,
                               version=0, qc_report={}, error=None) for n in range(1, 7)]
    db = AsyncMock()
    db.add = Mock()
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: lessons))
    db.get.return_value = SimpleNamespace(status="planned")
    monkeypatch.setattr(courses, "get_owned", AsyncMock(return_value=course))
    monkeypatch.setattr(courses.usage, "lock_user", AsyncMock())
    monkeypatch.setattr(courses.usage, "credit_cost", AsyncMock(return_value=10))
    monkeypatch.setattr(courses.usage, "check", AsyncMock())
    monkeypatch.setattr(courses, "pending_lesson_edit", AsyncMock(return_value=None))
    monkeypatch.setattr(courses, "run_inline_if_configured", AsyncMock())
    enqueue = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    monkeypatch.setattr(courses, "enqueue", enqueue)
    return db, user, course, lessons, enqueue


async def test_six_class_plan_builds_only_first_ppt(env):
    db, user, course, lessons, enqueue = env
    await courses.start_generation(db, user, course.id)
    enqueue.assert_awaited_once()
    assert enqueue.call_args.args[2]["lesson_id"] == str(lessons[0].id)
    assert all(lesson.status == "planned" for lesson in lessons[1:])
    assert courses.usage.check.call_args.args[3] == 10


@pytest.mark.parametrize("numbers", [[1, 2], [2]])
async def test_bulk_or_unreviewed_next_lesson_is_blocked(env, numbers):
    db, user, course, _, enqueue = env
    with pytest.raises(AppError) as exc:
        await courses.start_generation(db, user, course.id, numbers)
    assert exc.value.code == "review_required"
    enqueue.assert_not_awaited()
    courses.usage.check.assert_not_awaited()


async def test_approved_current_version_unlocks_next_lesson(env):
    db, user, course, lessons, enqueue = env
    first = lessons[0]
    first.status, first.pptx_key, first.version = "generated", "lesson.pptx", 2
    first.qc_report = {"approved_version": 2}
    await courses.start_generation(db, user, course.id)
    assert enqueue.call_args.args[2]["lesson_id"] == str(lessons[1].id)


async def test_rebuilt_version_needs_fresh_review(env):
    db, user, course, lessons, enqueue = env
    first = lessons[0]
    first.status, first.pptx_key, first.version = "generated", "lesson.pptx", 3
    first.qc_report = {"approved_version": 2}
    with pytest.raises(AppError):
        await courses.start_generation(db, user, course.id, [2])
    enqueue.assert_not_awaited()


@pytest.mark.parametrize("version,pending", [(1, False), (2, True)])
async def test_cannot_approve_stale_or_pending_ppt(env, monkeypatch, version, pending):
    db, user, _, lessons, _ = env
    lesson = lessons[0]
    lesson.status, lesson.pptx_key, lesson.version = "generated", "lesson.pptx", 2
    monkeypatch.setattr(courses, "get_owned", AsyncMock(return_value=lesson))
    monkeypatch.setattr(courses, "pending_lesson_edit", AsyncMock(return_value=object() if pending else None))
    with pytest.raises(AppError):
        await courses.approve_lesson(db, user, lesson.id, version)
    db.commit.assert_not_awaited()


async def test_approval_keeps_teacher_feedback(env, monkeypatch):
    db, user, _, lessons, _ = env
    lesson = lessons[0]
    lesson.status, lesson.pptx_key, lesson.version = "generated", "lesson.pptx", 2
    monkeypatch.setattr(courses, "get_owned", AsyncMock(return_value=lesson))
    await courses.approve_lesson(db, user, lesson.id, 2, "  More worked examples  ")
    assert lesson.qc_report["approved_version"] == 2
    assert lesson.qc_report["review_feedback"] == "More worked examples"
    db.commit.assert_awaited_once()


async def test_ai_inspects_all_pages_including_last_batch(monkeypatch):
    ai = SimpleNamespace(mode="live", structured=AsyncMock())
    ai.structured.side_effect = [styles.PageRoles(pages=[styles.PageRole(number=n, layout="worked_example")
                                                       for n in range(1, 9)]),
                                 styles.PageRoles(pages=[styles.PageRole(number=9, layout="quiz")])]
    monkeypatch.setattr(styles, "get_ai", lambda: ai)
    image = io.BytesIO()
    Image.new("RGB", (320, 180), "green").save(image, "PNG")
    monkeypatch.setattr(styles, "inspect", lambda *args, **kwargs:
                        SimpleNamespace(thumbnails=[image.getvalue()] * 9))
    spec = {"source_content": [{"number": n, "text": "Example"} for n in range(1, 10)],
            "page_variants": [{"number": n, "layout": "concept"} for n in range(1, 10)],
            "design_inspection": {}}
    await styles.inspect_page_roles(spec, uuid.uuid4(), b"source-pptx")
    assert len(spec["design_inspection"]["ai_page_roles"]) == 9
    assert spec["page_variants"][-1]["layout"] == "quiz"
    assert ai.structured.await_count == 2
    assert all(call.kwargs["images"][0].media_type == "image/jpeg" for call in ai.structured.await_args_list)


async def test_missing_page_inspection_is_rejected(monkeypatch):
    ai = SimpleNamespace(mode="live", structured=AsyncMock(return_value=styles.PageRoles(pages=[])))
    monkeypatch.setattr(styles, "get_ai", lambda: ai)
    spec = {"source_content": [{"number": 1}], "page_variants": [{"number": 1, "layout": "concept"}],
            "design_inspection": {}}
    with pytest.raises(ValueError, match="every source page"):
        await styles.inspect_page_roles(spec, uuid.uuid4())
