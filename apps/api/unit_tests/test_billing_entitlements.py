"""Payment status and monthly allowance boundaries without live charges."""
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.errors import AppError
from app.models import Subscription
from app.services import billing, usage


@pytest.mark.parametrize('payment_status', ['unpaid', None])
async def test_unsettled_checkout_never_grants_or_cancels_access(monkeypatch, payment_status):
    db = AsyncMock()
    event = {'type': 'checkout.session.completed', 'data': {'object': {
        'mode': 'subscription', 'payment_status': payment_status,
        'metadata': {'user_id': str(uuid.uuid4()), 'plan_code': 'pro'},
    }}}
    assert await billing.handle_stripe_event(db, event) == 'ignored'
    db.execute.assert_not_called()
    db.add.assert_not_called()


@pytest.mark.parametrize('status', ['incomplete', 'unpaid', 'paused'])
async def test_stripe_unpaid_statuses_do_not_become_entitled(monkeypatch, status):
    sub = Subscription(id=uuid.uuid4(), user_id=uuid.uuid4(), plan_code='pro', provider='stripe', status='active')
    monkeypatch.setattr(billing, '_find_sub', AsyncMock(return_value=sub))
    monkeypatch.setattr(billing._SubChanges, 'apply', AsyncMock())
    await billing.handle_stripe_event(AsyncMock(), {'type': 'customer.subscription.updated', 'data': {'object': {
        'id': 'sub_test', 'status': status,
    }}})
    assert sub.status == status
    assert sub.status not in usage.ACTIVE_STATUSES


@pytest.mark.parametrize('status', ['pending', 'on_hold'])
async def test_initial_dodo_payment_does_not_grant_paid_access(monkeypatch, status):
    sub = Subscription(id=uuid.uuid4(), user_id=uuid.uuid4(), plan_code='pro', provider='dodo', status='pending')
    monkeypatch.setattr(billing, '_find_sub', AsyncMock(return_value=sub))
    monkeypatch.setattr(billing, 'get_setting', AsyncMock(return_value={}))
    monkeypatch.setattr(billing._SubChanges, 'apply', AsyncMock())
    await billing.handle_dodo_event(AsyncMock(), {'type': f'subscription.{status}', 'data': {
        'subscription_id': 'sub_test', 'status': status,
    }})
    assert sub.status == 'pending'
    assert sub.status not in usage.ACTIVE_STATUSES


@pytest.mark.parametrize('provider', ['stripe', 'dodo', 'manual'])
async def test_existing_plan_prevents_a_second_checkout(monkeypatch, provider):
    db = AsyncMock()
    db.get.return_value = SimpleNamespace(code='pro', active=True)
    monkeypatch.setattr(billing, 'active_subscription', AsyncMock(return_value=SimpleNamespace(provider=provider)))
    monkeypatch.setattr(billing, 'pending_checkout', AsyncMock(return_value=None))
    gateway = AsyncMock()
    monkeypatch.setattr(billing, 'get_provider', gateway)
    with pytest.raises(AppError) as error:
        await billing.start_checkout(db, SimpleNamespace(id=uuid.uuid4()), 'pro', 'month')
    assert error.value.code == 'subscription_exists'
    gateway.assert_not_called()


async def test_payment_recovery_uses_portal_without_active_entitlements(monkeypatch):
    sub = SimpleNamespace(provider='stripe', provider_customer_id='cus_test', status='unpaid')
    monkeypatch.setattr(billing, 'manageable_online_subscription', AsyncMock(return_value=sub))
    provider = SimpleNamespace(portal=AsyncMock(return_value='https://billing.example/portal'))
    monkeypatch.setattr(billing, 'get_provider', AsyncMock(return_value=provider))
    assert await billing.open_portal(AsyncMock(), SimpleNamespace(id=uuid.uuid4())) == 'https://billing.example/portal'
    provider.portal.assert_awaited_once_with('cus_test')


async def test_manual_grant_cannot_overwrite_unresolved_gateway_subscription(monkeypatch):
    monkeypatch.setattr(billing, 'manageable_online_subscription', AsyncMock(return_value=SimpleNamespace(status='unpaid')))
    monkeypatch.setattr(billing, 'pending_checkout', AsyncMock(return_value=None))
    db = AsyncMock()
    with pytest.raises(AppError) as error:
        await billing.set_manual_plan(db, uuid.uuid4(), 'pro')
    assert error.value.code == 'paid_subscription'
    assert db.execute.await_count == 1  # shared plan change lock
    db.add.assert_not_called()


@pytest.mark.parametrize('provider,now,expected', [
    ('manual', datetime(2026, 3, 1, tzinfo=UTC), datetime(2026, 2, 28, tzinfo=UTC)),
    ('stripe', datetime(2026, 3, 31, tzinfo=UTC), datetime(2026, 3, 31, tzinfo=UTC)),
    ('dodo', datetime(2026, 4, 29, tzinfo=UTC), datetime(2026, 3, 31, tzinfo=UTC)),
    ('trial', datetime(2026, 3, 1, tzinfo=UTC), datetime(2026, 1, 31, tzinfo=UTC)),
])
def test_paid_allowances_reset_monthly_but_trial_is_one_allowance(monkeypatch, provider, now, expected):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(usage, 'datetime', Clock)
    sub = SimpleNamespace(provider=provider, current_period_start=datetime(2026, 1, 31, tzinfo=UTC))
    assert usage.period_start(sub) == expected


async def test_recovered_payment_is_recorded_paid_once():
    user_id = uuid.uuid4()
    row = SimpleNamespace(user_id=user_id, provider='stripe', status='failed', failure_reason='declined', invoice_url=None)
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: row))
    args = dict(user_id=user_id, provider='stripe', ref='in_test', amount=149,
                currency='AED', tax_amount=7.45, invoice_url='https://invoice.example')
    assert await billing._record_paid_payment(db, **args) is True
    assert row.status == 'paid' and row.failure_reason is None
    assert row.amount == 149 and row.invoice_url == args['invoice_url']
    assert await billing._record_paid_payment(db, **args) is False
    db.add.assert_not_called()
