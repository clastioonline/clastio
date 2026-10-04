from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.routes.auth import _maybe_start_trial


@pytest.mark.parametrize('role,enabled,subscription', [('admin', True, None), ('teacher', False, None), ('teacher', True, object())])
async def test_trial_rejects_disabled_staff_and_existing_subscription(monkeypatch, role, enabled, subscription):
    monkeypatch.setattr('app.services.settings.get_setting', AsyncMock(return_value={'enabled': enabled, 'days': 7, 'plan': 'pro'}))
    monkeypatch.setattr('app.services.usage.active_subscription', AsyncMock(return_value=subscription))
    db = AsyncMock()
    assert await _maybe_start_trial(db, SimpleNamespace(id='test', role=role, email_verified=True), None) is False
    assert db.execute.await_count == (1 if role == 'teacher' and enabled else 0)

async def test_trial_prevents_reusing_previous_grant(monkeypatch):
    monkeypatch.setattr('app.services.settings.get_setting', AsyncMock(return_value={'enabled': True, 'days': 7, 'plan': 'pro'}))
    monkeypatch.setattr('app.services.usage.active_subscription', AsyncMock(return_value=None))
    monkeypatch.setattr('app.services.billing.manageable_online_subscription', AsyncMock(return_value=None))
    monkeypatch.setattr('app.services.billing.pending_checkout', AsyncMock(return_value=None))
    start = AsyncMock()
    monkeypatch.setattr('app.services.usage.start_trial', start)
    monkeypatch.setattr('app.api.routes.auth.security_event', lambda *args, **kwargs: None)
    db = AsyncMock()
    db.get.return_value = object()
    db.execute.return_value = SimpleNamespace(rowcount=0)
    import uuid
    assert await _maybe_start_trial(db, SimpleNamespace(id=uuid.uuid4(), role='teacher', email='teacher@example.com', email_verified=True), None) is False
    start.assert_not_called()


async def test_trial_requires_verified_email_before_grant_or_lock(monkeypatch):
    from app.core.errors import AppError

    monkeypatch.setattr('app.services.settings.get_setting', AsyncMock(return_value={'enabled': True, 'days': 7, 'plan': 'pro'}))
    db = AsyncMock()
    with pytest.raises(AppError) as error:
        await _maybe_start_trial(db, SimpleNamespace(id='test', role='teacher', email_verified=False), None)
    assert error.value.code == 'email_unverified'
    db.execute.assert_not_called()
