"""Clerk role changes must survive the account request that discovers them."""
import copy
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings
from app.core.deps import get_current_user, staff_permissions
from app.core.errors import AppError


@pytest.mark.parametrize('before,metadata,expected', [
    (('teacher', None), {'role': 'admin', 'admin_role': 'super_admin'}, ('admin', 'super_admin')),
    (('admin', 'super_admin'), {}, ('teacher', None)),
])
async def test_account_refresh_persists_staff_role_for_following_request(monkeypatch, before, metadata, expected):
    ident = uuid.uuid4()
    user = SimpleNamespace(id=ident, status='active', role=before[0], admin_role=before[1])
    saved = copy.copy(user)
    db = AsyncMock()
    db.get.side_effect = lambda *args: copy.copy(saved)
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: SimpleNamespace(subject='user_test')))

    def save_role():
        saved.role, saved.admin_role = current[0].role, current[0].admin_role

    # Keep a simulated stored record distinct from each request's loaded user.
    current = [user]
    def load_user(*args):
        current[0] = copy.copy(saved)
        return current[0]
    db.get.side_effect = load_user
    db.commit.side_effect = save_role
    settings = get_settings()
    monkeypatch.setattr(settings, 'clerk_secret_key', 'sk_test_fake')
    monkeypatch.setattr('app.core.deps.decode_token', lambda token: {'sub': str(ident), 'sid': str(uuid.uuid4())})
    monkeypatch.setattr('app.services.sessions.load_active', AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4(), method='clerk')))
    monkeypatch.setattr('app.services.sessions.touch', AsyncMock())
    remote = AsyncMock()
    remote.__aenter__.return_value = remote
    remote.get.return_value = httpx.Response(200, json={'public_metadata': metadata})
    monkeypatch.setattr('httpx.AsyncClient', lambda **kwargs: remote)

    account = Request({'type': 'http', 'path': '/api/v1/auth/me', 'headers': [(b'authorization', b'Bearer fake')]})
    refreshed = await get_current_user(account, db)
    assert (refreshed.role, refreshed.admin_role) == expected
    assert (saved.role, saved.admin_role) == expected
    assert db.commit.await_count == 1

    subsequent = Request({'type': 'http', 'path': '/api/v1/admin/licenses', 'headers': [(b'authorization', b'Bearer fake')]})
    loaded = await get_current_user(subsequent, db)
    assert bool(staff_permissions(loaded)) is (expected[0] == 'admin')


@pytest.mark.parametrize('status,reason', [(200, 'clerk_banned'), (404, 'clerk_deleted')])
async def test_unavailable_clerk_admin_revokes_existing_app_sessions(monkeypatch, status, reason):
    ident = uuid.uuid4()
    user = SimpleNamespace(id=ident, status='active', role='admin', admin_role='super_admin')
    db = AsyncMock()
    db.get.return_value = user
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: SimpleNamespace(subject='user_test')))
    monkeypatch.setattr(get_settings(), 'clerk_secret_key', 'sk_test_fake')
    monkeypatch.setattr('app.core.deps.decode_token', lambda token: {'sub': str(ident), 'sid': str(uuid.uuid4())})
    monkeypatch.setattr('app.services.sessions.load_active', AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4(), method='clerk')))
    revoke = AsyncMock()
    monkeypatch.setattr('app.services.sessions.revoke', revoke)
    remote = AsyncMock()
    remote.__aenter__.return_value = remote
    remote.get.return_value = httpx.Response(status, json={'banned': True, 'public_metadata': {'role': 'admin'}})
    monkeypatch.setattr('httpx.AsyncClient', lambda **kwargs: remote)
    request = Request({'type': 'http', 'path': '/api/v1/admin/licenses', 'headers': [(b'authorization', b'Bearer fake')]})
    with pytest.raises(HTTPException) as error:
        await get_current_user(request, db)
    assert error.value.status_code == 403
    revoke.assert_awaited_once_with(db, ident, reason=reason)
    db.commit.assert_awaited_once()


async def test_legacy_password_session_cannot_inherit_clerk_staff_privileges(monkeypatch):
    ident = uuid.uuid4()
    user = SimpleNamespace(id=ident, status='active', role='admin', admin_role='super_admin')
    db = AsyncMock()
    db.get.return_value = user
    monkeypatch.setattr(get_settings(), 'clerk_secret_key', 'sk_test_fake')
    monkeypatch.setattr('app.core.deps.decode_token', lambda token: {'sub': str(ident), 'sid': str(uuid.uuid4())})
    monkeypatch.setattr('app.services.sessions.load_active', AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4(), method='password')))
    request = Request({'type': 'http', 'path': '/api/v1/admin/licenses', 'headers': [(b'authorization', b'Bearer fake')]})
    with pytest.raises(HTTPException) as error:
        await get_current_user(request, db)
    assert error.value.status_code == 403
    assert 'Clerk' in error.value.detail
    db.execute.assert_not_called()


async def test_teacher_api_calls_check_clerk_at_most_once_per_minute_and_detect_bans(monkeypatch):
    from datetime import timedelta

    ident = uuid.uuid4()
    user = SimpleNamespace(id=ident, status='active', role='teacher', admin_role=None, clerk_checked_at=None)
    db = AsyncMock()
    db.get.return_value = user
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: SimpleNamespace(subject='user_test')))
    monkeypatch.setattr(get_settings(), 'clerk_secret_key', 'sk_test_fake')
    monkeypatch.setattr('app.core.deps.decode_token', lambda token: {'sub': str(ident), 'sid': str(uuid.uuid4())})
    monkeypatch.setattr('app.services.sessions.load_active', AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4(), method='clerk')))
    monkeypatch.setattr('app.services.sessions.touch', AsyncMock())
    revoke = AsyncMock()
    monkeypatch.setattr('app.services.sessions.revoke', revoke)
    remote = AsyncMock()
    remote.__aenter__.return_value = remote
    remote.get.return_value = httpx.Response(200, json={'public_metadata': {}})
    monkeypatch.setattr('httpx.AsyncClient', lambda **kwargs: remote)
    request = Request({'type': 'http', 'path': '/api/v1/courses', 'headers': [(b'authorization', b'Bearer fake')]})
    for _ in range(2):
        assert await get_current_user(request, db) is user
    assert remote.get.await_count == 1
    user.clerk_checked_at -= timedelta(seconds=61)
    remote.get.return_value = httpx.Response(200, json={'banned': True})
    with pytest.raises(HTTPException) as error:
        await get_current_user(request, db)
    assert error.value.status_code == 403
    revoke.assert_awaited_once_with(db, ident, reason='clerk_banned')


@pytest.mark.parametrize('banned', [False, True])
async def test_verified_clerk_link_confirms_local_email_and_banned_identity_is_refused(monkeypatch, banned):
    import jwt

    from app.api.routes import auth

    settings = get_settings()
    monkeypatch.setattr(settings, 'clerk_secret_key', 'sk_test_fake')
    monkeypatch.setattr(settings, 'clerk_issuer', 'https://clerk.example.com')
    monkeypatch.setattr(settings, 'clerk_jwt_key', 'test_key_not_used')
    monkeypatch.setattr(jwt, 'decode', lambda *args, **kwargs: {'sub': 'user_test', 'azp': settings.public_web_url.rstrip('/')})
    user = SimpleNamespace(id=uuid.uuid4(), email='teacher@example.com', email_verified=False,
                           email_verified_at=None, role='teacher', admin_role=None, status='active')
    db = AsyncMock()
    def result(value):
        return SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: value))
    db.execute.side_effect = [None, result(None), result(user)]
    db.add = lambda *args: None
    monkeypatch.setattr(auth, 'decode_token', lambda token: {'sub': str(user.id), 'sid': 'existing'})
    monkeypatch.setattr('app.services.sessions.load_active', AsyncMock(return_value=object()))
    monkeypatch.setattr('app.services.sessions.start_session', AsyncMock())
    monkeypatch.setattr(auth, 'security_event', lambda *args, **kwargs: None)
    monkeypatch.setattr(auth, '_load', AsyncMock(return_value=user))
    monkeypatch.setattr(auth, 'user_out', lambda row: {'email_verified': row.email_verified})
    remote = AsyncMock()
    remote.__aenter__.return_value = remote
    remote.get.return_value = httpx.Response(200, json={
        'banned': banned, 'primary_email_address_id': 'email_test',
        'email_addresses': [{'id': 'email_test', 'email_address': user.email, 'verification': {'status': 'verified'}}],
    })
    monkeypatch.setattr('httpx.AsyncClient', lambda **kwargs: remote)
    request = Request({'type': 'http', 'headers': [(b'cookie', b'ata_session=existing')]})
    if banned:
        with pytest.raises(AppError) as error:
            await auth.clerk_login(auth.ClerkLoginIn(token='fake'), request, Response(), db)
        assert error.value.status == 403
        db.execute.assert_not_called()
    else:
        linked = await auth.clerk_login(auth.ClerkLoginIn(token='fake'), request, Response(), db)
        assert linked['user']['email_verified'] is True
        assert user.email_verified_at is not None
        db.commit.assert_awaited_once()
