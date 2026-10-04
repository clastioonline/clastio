import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.services import assistant


def test_brief_limits():
    with pytest.raises(ValidationError):
        assistant.PPTBrief(topic='Fractions', grade='6', subject='Maths', instructions='Learn fractions', slides_per_lecture=100)


async def test_playground_never_runs_generation_actions(monkeypatch):
    conv = SimpleNamespace(id=uuid.uuid4(), owner_id=uuid.uuid4(), channel='playground')
    user = SimpleNamespace(id=conv.owner_id)
    db = AsyncMock()
    db.get.return_value = conv
    row = SimpleNamespace(role='user', content='Create fractions slides', actions=[])
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [row]))
    saved = []
    db.add = saved.append
    classify = AsyncMock(side_effect=AssertionError('Planning must not run actions'))
    monkeypatch.setattr(assistant, 'classify', classify)
    monkeypatch.setattr(assistant, 'build_context', AsyncMock(return_value=('Grade 6 teacher', [])))
    result = assistant.PlaygroundReply(reply='Review this draft.', brief=assistant.PPTBrief(topic='Fractions', grade='6', subject='Maths', instructions='Compare fractions using bars and an exit ticket.'))
    monkeypatch.setattr(assistant, 'get_ai', lambda: SimpleNamespace(structured=AsyncMock(return_value=result)))
    events = [e async for e in assistant.converse(db, user, row.content, conv.id, record_user=False)]
    classify.assert_not_awaited()
    assert saved[-1].actions[0]['brief']['topic'] == 'Fractions'
    assert saved[-1].actions[1]['href'] == f'/projects/new?brief={conv.id}'
    assert events[-1]['event'] == 'done'
