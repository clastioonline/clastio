"""Offline application-level regression; not a production infrastructure benchmark."""
import asyncio
import time
import uuid

import httpx
import pytest

from app.core.db import get_sessionmaker
from app.models import User
from app.services.sessions import start_session


@pytest.mark.asyncio
async def test_one_hundred_authenticated_users(app, seeded):
    tokens = []
    async with get_sessionmaker()() as db:
        for _ in range(100):
            user = User(email=f'capacity-{uuid.uuid4().hex}@example.com', name='Capacity test', email_verified=True)
            db.add(user)
            await db.flush()
            _, token = await start_session(db, user, None, None)
            tokens.append(token)
        await db.commit()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test', timeout=60) as client:
        started = time.monotonic()
        async def visit(token):
            headers = {'Authorization': f'Bearer {token}'}
            for route in ['/api/v1/auth/me', '/api/v1/projects']:
                response = await client.get(route, headers=headers)
                assert response.status_code == 200, response.text
        await asyncio.gather(*(visit(token) for token in tokens))
    print(f'100 authenticated users, 200 requests: {time.monotonic() - started:.2f}s; ASGI/offline, real PostgreSQL')
