"""Provider boundary tests that don't require PostgreSQL or network access."""
import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.requests import Request
from starlette.responses import Response

from app.api.routes.auth import ClerkLoginIn, clerk_login
from app.core.config import get_settings
from app.core.errors import AppError
from app.services.notify import send_pending_emails


@pytest.mark.parametrize('claims', [dict(azp='https://attacker.example'), dict(iss='https://wrong.example'),
                                     dict(exp=1), dict(sts='pending'), dict(sub='user_../bad')])
async def test_invalid_clerk_tokens_fail_before_database_or_network(monkeypatch, claims):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    settings = get_settings()
    monkeypatch.setattr(settings, 'clerk_secret_key', 'sk_test_fake')
    monkeypatch.setattr(settings, 'clerk_issuer', 'https://clerk.example.com')
    monkeypatch.setattr(settings, 'clerk_jwt_key', key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode())
    now = int(time.time())
    token = jwt.encode(dict(sub='user_test', iss=settings.clerk_issuer, azp=settings.public_web_url,
                            iat=now, nbf=now-1, exp=now+60) | claims, key, algorithm='RS256')
    with pytest.raises(AppError) as error:
        await clerk_login(ClerkLoginIn(token=token), Request({'type': 'http', 'headers': []}), Response(), None)
    assert error.value.code == 'clerk_invalid'


@pytest.mark.parametrize('status', [200, 429])
async def test_resend_worker_payload_and_retry(monkeypatch, status):
    settings = get_settings()
    monkeypatch.setattr(settings, 'resend_api_key', 're_fake')
    row = SimpleNamespace(id=uuid.uuid4(), attempts=0, to_email='recipient@example.com',
                          subject='Welcome', body_text='Hello', status='queued', template='welcome')
    db = AsyncMock()
    db.__aenter__.return_value = db
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [row]))
    monkeypatch.setattr('app.services.notify.get_sessionmaker', lambda: lambda: db)
    remote = AsyncMock()
    remote.__aenter__.return_value = remote
    remote.post.return_value = httpx.Response(status)
    monkeypatch.setattr('app.services.notify.httpx.AsyncClient', lambda **kwargs: remote)
    sent = await send_pending_emails()
    args = remote.post.call_args.kwargs
    assert args['headers']['Idempotency-Key'] == f'outbox/{row.id}'
    assert args['json']['to'] == ['recipient@example.com']
    assert args['json']['text'] == 'Hello'
    assert sent == (1 if status == 200 else 0)
    assert row.status == ('sent' if status == 200 else 'queued')
    if status == 429:
        assert '429' in row.last_error and 're_fake' not in row.last_error
