from __future__ import annotations

import time
from unittest.mock import AsyncMock

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.models import EmailOutbox, OAuthAccount
from app.services.notify import queue_email, send_pending_emails
from tests.conftest import make_user


@pytest.fixture
def clerk(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    settings = get_settings()
    monkeypatch.setattr(settings, 'clerk_secret_key', 'sk_test_fake')
    monkeypatch.setattr(settings, 'clerk_issuer', 'https://clerk.example.com')
    monkeypatch.setattr(settings, 'clerk_jwt_key', private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode())
    def token(**overrides):
        now = int(time.time())
        return jwt.encode({'sub': 'user_test', 'iss': settings.clerk_issuer, 'azp': settings.public_web_url,
                           'iat': now, 'nbf': now - 1, 'exp': now + 60, **overrides}, private, algorithm='RS256')
    return token


def mock_clerk(monkeypatch, email, verified=True):
    remote = AsyncMock()
    remote.get.return_value = httpx.Response(200, json={
        'primary_email_address_id': 'email_1', 'first_name': 'Clerk', 'last_name': 'Teacher',
        'email_addresses': [{'id': 'email_1', 'email_address': email,
                             'verification': {'status': 'verified' if verified else 'unverified'}}]})
    remote.__aenter__.return_value = remote
    monkeypatch.setattr('app.api.routes.auth.httpx.AsyncClient', lambda **kwargs: remote)
    return remote


@pytest.mark.parametrize('claims', [{'azp': 'https://attacker.example'}, {'iss': 'https://wrong.example'},
                                     {'exp': 1}, {'sts': 'pending'}])
async def test_clerk_rejects_invalid_session(client, clerk, claims):
    result = await client.post('/api/v1/auth/clerk', json={'token': clerk(**claims)})
    assert result.status_code == 401


async def test_clerk_signup_terms_and_identity(client, clerk, monkeypatch):
    import uuid
    mock_clerk(monkeypatch, f'clerk-{uuid.uuid4().hex}@example.com')
    result = await client.post('/api/v1/auth/clerk', json={'token': clerk()})
    assert result.status_code == 422
    result = await client.post('/api/v1/auth/clerk', json={'token': clerk(), 'accept_terms': True})
    assert result.status_code == 200, result.text
    user_id = result.json()['user']['id']
    assert result.json()['user']['email_verified']
    assert (await client.get('/api/v1/auth/me')).status_code == 200
    result = await client.post('/api/v1/auth/clerk', json={'token': clerk()})
    assert result.json()['user']['id'] == user_id
    async with get_sessionmaker()() as db:
        links = (await db.execute(select(OAuthAccount).where(OAuthAccount.subject == 'user_test'))).scalars().all()
        assert len(links) == 1


async def test_existing_account_requires_original_session(client, clerk, monkeypatch):
    user = await make_user(client)
    mock_clerk(monkeypatch, user['email'])
    result = await client.post('/api/v1/auth/clerk', json={'token': clerk(sub='user_existing')})
    assert result.status_code == 409
    assert result.json()['error']['code'] == 'clerk_link_required'
    result = await client.post('/api/v1/auth/login', json={'email': user['email'], 'password': 'correct-horse-1'})
    assert result.status_code == 200
    result = await client.post('/api/v1/auth/clerk', json={'token': clerk(sub='user_existing')})
    assert result.status_code == 200, result.text
    assert result.json()['user']['id'] == user['id']


async def test_clerk_rejects_unverified_email(client, clerk, monkeypatch):
    mock_clerk(monkeypatch, 'unverified@example.com', verified=False)
    result = await client.post('/api/v1/auth/clerk', json={'token': clerk()})
    assert result.status_code == 403


async def test_resend_delivery_and_retry(monkeypatch, database):
    settings = get_settings()
    monkeypatch.setattr(settings, 'resend_api_key', 're_fake')
    remote = AsyncMock()
    remote.__aenter__.return_value = remote
    remote.post.return_value = httpx.Response(200, json={'id': 'email_sent'})
    monkeypatch.setattr('app.services.notify.httpx.AsyncClient', lambda **kwargs: remote)
    async with get_sessionmaker()() as db:
        # Avoid unrelated welcome emails from earlier test cases.
        existing = (await db.execute(select(EmailOutbox).where(EmailOutbox.status == 'queued'))).scalars().all()
        for row in existing:
            row.status = 'logged'
        row = queue_email(db, None, 'welcome', to='recipient@example.com', link='https://clastio.online/dashboard')
        await db.commit()
        row_id = row.id
    assert await send_pending_emails() == 1
    args = remote.post.call_args.kwargs
    assert args['headers']['Idempotency-Key'] == f'outbox/{row_id}'
    assert args['json']['to'] == ['recipient@example.com']
    async with get_sessionmaker()() as db:
        row = await db.get(EmailOutbox, row_id)
        assert row.status == 'sent'
        row.status = 'queued'
        await db.commit()
    remote.post.return_value = httpx.Response(429)
    assert await send_pending_emails() == 0
    async with get_sessionmaker()() as db:
        row = await db.get(EmailOutbox, row_id)
        assert row.status == 'queued'
        assert '429' in row.last_error
        assert 're_fake' not in row.last_error
