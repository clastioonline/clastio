"""Checkout and plan-change serialization against the isolated PostgreSQL DB."""
import asyncio
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.db import get_sessionmaker, utcnow
from app.models import SubscriptionCheckout
from app.services import billing
from tests.conftest import make_staff
from tests.test_plan_licenses import issue, verified_teacher


async def test_concurrent_checkouts_cannot_create_two_provider_sessions(client, monkeypatch):
    teacher = await verified_teacher(client)
    started, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def create(*args, reservation, **kwargs):
        calls.append(reservation.id)
        started.set()
        await release.wait()
        return billing.CreatedCheckout('cs_concurrent', 'https://checkout.example/one', utcnow()+timedelta(hours=24))

    monkeypatch.setattr(billing, 'get_provider', AsyncMock(return_value=SimpleNamespace(name='dodo', checkout=create)))
    first = asyncio.create_task(client.post('/api/v1/billing/checkout', headers=teacher['headers'],
        json={'plan': 'pro', 'interval': 'month'}))
    try:
        await asyncio.wait_for(started.wait(), 5)
        # The first request is still awaiting the provider, but its durable
        # reservation must already block a request on another DB connection.
        second = await asyncio.wait_for(client.post('/api/v1/billing/checkout', headers=teacher['headers'],
            json={'plan': 'assistant', 'interval': 'year'}), 5)
        assert second.status_code == 409, second.text
    finally:
        release.set()
    first_result = await asyncio.wait_for(first, 5)
    assert first_result.status_code == 200, first_result.text
    resumed = await client.post('/api/v1/billing/checkout', headers=teacher['headers'],
        json={'plan': 'assistant', 'interval': 'year'})
    assert resumed.status_code == 200 and resumed.json() == first_result.json()
    assert len(calls) == 1
    async with get_sessionmaker()() as db:
        rows = (await db.execute(select(SubscriptionCheckout).where(
            SubscriptionCheckout.user_id == uuid.UUID(teacher['id'])))).scalars().all()
        assert len(rows) == 1 and rows[0].status == 'open'
        assert rows[0].plan_code == 'pro'


async def test_pending_checkout_blocks_trial_license_and_manual_plan(client):
    teacher = await verified_teacher(client)
    admin = await make_staff(client)
    license = await issue(client, admin)
    async with get_sessionmaker()() as db:
        db.add(SubscriptionCheckout(user_id=uuid.UUID(teacher['id']), provider='stripe', plan_code='pro',
            interval='month', status='creating', expires_at=utcnow()+timedelta(hours=1)))
        await db.commit()
    results = await asyncio.gather(
        client.post('/api/v1/auth/trial', headers=teacher['headers']),
        client.post('/api/v1/billing/licenses/redeem', headers=teacher['headers'], json={'key': license['key']}),
    )
    assert [r.status_code for r in results] == [409, 409]
    from app.core.errors import AppError

    async with get_sessionmaker()() as db:
        with pytest.raises(AppError) as error:
            await billing.set_manual_plan(db, uuid.UUID(teacher['id']), 'pro')
        assert error.value.code == 'paid_subscription'
    state = await client.get('/api/v1/billing/subscription', headers=teacher['headers'])
    assert state.status_code == 200, state.text
    assert state.json()['trial_available'] is False
    assert state.json()['pending_checkout']['status'] == 'creating'


async def test_database_constraint_prevents_two_pending_checkouts(client):
    teacher = await verified_teacher(client)
    # This remains enforced even if a future caller forgets the advisory lock.
    async with get_sessionmaker()() as db:
        for provider in ('stripe', 'dodo'):
            db.add(SubscriptionCheckout(user_id=uuid.UUID(teacher['id']), provider=provider, plan_code='pro',
                interval='month', status='open', expires_at=utcnow()+timedelta(hours=24)))
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()


async def test_billing_releases_only_a_provider_confirmed_expired_checkout(client, monkeypatch):
    teacher = await verified_teacher(client)
    async with get_sessionmaker()() as db:
        row = SubscriptionCheckout(user_id=uuid.UUID(teacher['id']), provider='stripe', plan_code='pro',
            interval='month', status='open', provider_session_id='cs_expired',
            checkout_url='https://checkout.example/expired', expires_at=utcnow()-timedelta(minutes=1))
        db.add(row)
        await db.commit()
        row_id = row.id
    provider = SimpleNamespace(name='stripe', checkout_state=AsyncMock(return_value='expired'))
    monkeypatch.setattr(billing, 'get_provider', AsyncMock(return_value=provider))
    state = await client.get('/api/v1/billing/subscription', headers=teacher['headers'])
    assert state.status_code == 200 and state.json()['pending_checkout'] is None
    provider.checkout_state.assert_awaited_once()
    async with get_sessionmaker()() as db:
        assert (await db.get(SubscriptionCheckout, row_id)).status == 'expired'
