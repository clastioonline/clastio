import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.errors import AppError, NotFound
from app.generation.specs import SlideSpec
from app.services import courses


@pytest.fixture
def edit_environment(monkeypatch):
    owner, lid = uuid.uuid4(), uuid.uuid4()
    user = SimpleNamespace(id=owner)
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: SimpleNamespace(version=1)))
    monkeypatch.setattr(courses, 'get_owned', AsyncMock(return_value=SimpleNamespace(id=lid)))
    monkeypatch.setattr(courses.usage, 'lock_user', AsyncMock())
    monkeypatch.setattr(courses.usage, 'check', AsyncMock())
    monkeypatch.setattr(courses.usage, 'credit_cost', AsyncMock(return_value=2))
    monkeypatch.setattr(courses, 'pending_lesson_edit', AsyncMock(return_value=None))
    job = SimpleNamespace(id=uuid.uuid4())
    enqueue = AsyncMock(return_value=job)
    monkeypatch.setattr(courses, 'enqueue', enqueue)
    monkeypatch.setattr(courses, 'run_inline_if_configured', AsyncMock())
    return db, user, lid, enqueue


async def test_identical_pending_edit_returns_same_job_without_reserving_twice(edit_environment, monkeypatch):
    db, user, lid, enqueue = edit_environment
    pending = SimpleNamespace(id=uuid.uuid4(), type='slide_regeneration', payload={'slide_number': 2, 'instruction': 'Shorten the example', 'keep_images': True})
    monkeypatch.setattr(courses, 'pending_lesson_edit', AsyncMock(return_value=pending))
    result = await courses.regenerate_slide(db, user, lid, 2, action=None, instruction='Shorten the example')
    assert result == pending.id
    enqueue.assert_not_awaited()
    courses.usage.check.assert_not_awaited()


async def test_conflicting_edit_is_blocked(edit_environment, monkeypatch):
    db, user, lid, enqueue = edit_environment
    monkeypatch.setattr(courses, 'pending_lesson_edit', AsyncMock(return_value=SimpleNamespace(type='lesson_render')))
    with pytest.raises(AppError) as exc:
        await courses.regenerate_slide(db, user, lid, 2, action=None, instruction='Shorten')
    assert exc.value.code == 'edit_pending'
    enqueue.assert_not_awaited()


async def test_missing_slide_does_not_reserve_credits(edit_environment):
    db, user, lid, enqueue = edit_environment
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: None))
    with pytest.raises(NotFound):
        await courses.regenerate_slide(db, user, lid, 999, action=None, instruction='Shorten')
    courses.usage.check.assert_not_awaited()


async def test_edit_reserves_configured_cost_and_has_no_paid_retry(edit_environment):
    db, user, lid, enqueue = edit_environment
    await courses.regenerate_slide(db, user, lid, 2, action=None, instruction='Shorten')
    assert enqueue.call_args.kwargs['credits_reserved'] == 2
    assert enqueue.call_args.kwargs['max_attempts'] == 1
    assert enqueue.call_args.args[2]['keep_images'] is True
    assert enqueue.call_args.args[2]['credit_cost'] == 2


@pytest.mark.parametrize('changed', [False, True])
async def test_worker_preserves_images_and_charges_only_changed_slide(monkeypatch, changed):
    lid, owner = uuid.uuid4(), uuid.uuid4()
    old = SlideSpec(number=1, layout='image_text', purpose='Explain', title='Leaves', asset_id=str(uuid.uuid4()), visual={'kind': 'image', 'description': 'Green leaf'}, sources=[{'type': 'image', 'source': 'upload'}])
    other = SlideSpec(number=2, layout='summary', purpose='Summarise', title='Recap')
    deck = SimpleNamespace(slides=[old, other])
    new = old.model_copy(deep=True)
    new.visual.description = 'Unrequested replacement'
    new.asset_id = None
    if changed:
        new.title = 'How leaves work'
    db = AsyncMock()
    db.__aenter__.return_value = db
    db.get.side_effect = [SimpleNamespace(course_id=uuid.uuid4(), owner_id=owner), SimpleNamespace(topic='Plants', class_section_id=None, subject='Science', grade='6', template_id=None, options={}), SimpleNamespace(id=owner)]
    monkeypatch.setattr(courses, 'get_sessionmaker', lambda: lambda: db)
    monkeypatch.setattr(courses, 'load_deck', AsyncMock(return_value=deck))
    monkeypatch.setattr(courses, 'resolve_template', AsyncMock(return_value=SimpleNamespace(spec={})))
    monkeypatch.setattr(courses, 'compute_budgets', lambda spec: {})
    monkeypatch.setattr(courses, 'build_context', AsyncMock(return_value=('Relevant source material', {})))
    monkeypatch.setattr(courses, 'get_ai', lambda: object())
    monkeypatch.setattr(courses.pipeline, 'repair_slide', AsyncMock(return_value=new))
    monkeypatch.setattr(courses.pipeline, 'enforce_budgets', lambda slide, budget: slide)
    render = AsyncMock(return_value={'version': 2})
    monkeypatch.setattr(courses, 'rerender_lesson', render)
    consume = AsyncMock()
    monkeypatch.setattr(courses.usage, 'consume', consume)
    monkeypatch.setattr(courses.usage, 'credit_cost', AsyncMock(return_value=99))
    ctx = SimpleNamespace(payload={'lesson_id': str(lid), 'slide_number': 1, 'instruction': 'Shorten', 'credit_cost': 2}, job_id=uuid.uuid4(), progress=AsyncMock())
    result = await courses.handle_slide_regeneration(ctx)
    assert result['changed'] is changed
    assert result['credits_used'] == (2 if changed else 0)
    assert deck.slides[0].asset_id == old.asset_id
    assert deck.slides[0].visual.description == 'Green leaf'
    assert deck.slides[1] is other
    if changed:
        assert consume.call_args.args[2] == 2
        render.assert_awaited_once()
    else:
        consume.assert_not_awaited()
        render.assert_not_awaited()
