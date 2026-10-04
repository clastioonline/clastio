"""Durable checkout reuse, uncertain outcomes and authoritative expiry."""
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.db import utcnow
from app.core.errors import AppError
from app.models import Plan, SubscriptionCheckout
from app.services import billing


def checkout_fixture(monkeypatch, provider_name='stripe'):
    stored = []
    db = AsyncMock()
    db.add = stored.append
    plan = Plan(code='pro', name='Pro', active=True, price_monthly_aed=249)
    db.get.side_effect = lambda model, ident, **kwargs: plan if model is Plan else next((r for r in stored if r.id == ident), None)
    monkeypatch.setattr(billing, 'lock_plan_changes', AsyncMock())
    monkeypatch.setattr(billing, 'active_subscription', AsyncMock(return_value=None))
    monkeypatch.setattr(billing, 'manageable_online_subscription', AsyncMock(return_value=None))
    monkeypatch.setattr(billing, 'pending_checkout', AsyncMock(side_effect=lambda *args, **kwargs: next(
        (r for r in stored if r.status in billing.PENDING_CHECKOUT_STATUSES), None)))
    provider = SimpleNamespace(name=provider_name, checkout=AsyncMock())
    monkeypatch.setattr(billing, 'get_provider', AsyncMock(return_value=provider))
    return db, stored, provider, SimpleNamespace(id=uuid.uuid4(), email='teacher@example.com')


async def test_repeat_checkout_returns_the_stored_url_without_another_provider_call(monkeypatch):
    db, stored, provider, user = checkout_fixture(monkeypatch)
    provider.checkout.return_value = billing.CreatedCheckout('cs_test', 'https://checkout.example/session', utcnow()+timedelta(hours=1))
    first = await billing.start_checkout(db, user, 'pro', 'month', 'SAVE20')
    assert stored[0].status == 'open'
    assert db.commit.await_count == 2  # reservation first, then published URL
    second = await billing.start_checkout(db, user, 'assistant', 'year', 'OTHER')
    assert second == first
    assert len(stored) == 1 and provider.checkout.await_count == 1


async def test_uncertain_dodo_creation_remains_reserved_and_cannot_create_another(monkeypatch):
    db, stored, provider, user = checkout_fixture(monkeypatch, 'dodo')
    provider.checkout.side_effect = httpx.ReadTimeout('response lost')
    with pytest.raises(AppError) as error:
        await billing.start_checkout(db, user, 'pro', 'month')
    assert error.value.code == 'checkout_unavailable'
    assert stored[0].status == 'creating'
    with pytest.raises(AppError) as error:
        await billing.start_checkout(db, user, 'assistant', 'year')
    assert error.value.code == 'checkout_in_progress'
    assert provider.checkout.await_count == 1 and len(stored) == 1


async def test_preparation_failure_before_submission_releases_a_fresh_reservation(monkeypatch):
    db, stored, provider, user = checkout_fixture(monkeypatch, 'dodo')
    provider.checkout.side_effect = AppError('billing_preparation_unavailable', 'Price lookup timed out', 503)
    with pytest.raises(AppError):
        await billing.start_checkout(db, user, 'pro', 'month')
    assert stored[0].status == 'failed'
    provider.checkout.side_effect = None
    provider.checkout.return_value = billing.CreatedCheckout('cs_retry', 'https://checkout.example/retry', utcnow()+timedelta(hours=24))
    assert await billing.start_checkout(db, user, 'pro', 'month') == 'https://checkout.example/retry'
    assert len(stored) == 2


async def test_uncertain_stripe_creation_retries_the_same_operation_and_plan(monkeypatch):
    db, stored, provider, user = checkout_fixture(monkeypatch)
    provider.checkout.side_effect = [httpx.ReadTimeout('response lost'),
        billing.CreatedCheckout('cs_test', 'https://checkout.example/session', utcnow()+timedelta(hours=1))]
    with pytest.raises(AppError):
        await billing.start_checkout(db, user, 'pro', 'month', 'SAVE20')
    assert await billing.start_checkout(db, user, 'assistant', 'year', 'OTHER') == 'https://checkout.example/session'
    assert len(stored) == 1
    first, retry = provider.checkout.await_args_list
    assert first.kwargs['reservation'].id == retry.kwargs['reservation'].id
    assert retry.args[1].code == 'pro' and retry.args[2] == 'month'
    assert retry.kwargs['coupon_code'] == 'SAVE20'


@pytest.mark.parametrize('state,still_pending', [('processing', True), ('expired', False)])
async def test_local_expiry_cannot_release_a_checkout_without_provider_confirmation(monkeypatch, state, still_pending):
    row = SubscriptionCheckout(id=uuid.uuid4(), user_id=uuid.uuid4(), provider='stripe', plan_code='pro', interval='month',
        status='open', provider_session_id='cs_test', expires_at=utcnow()-timedelta(seconds=1))
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: row))
    provider = SimpleNamespace(checkout_state=AsyncMock(return_value=state))
    monkeypatch.setattr(billing, 'get_provider', AsyncMock(return_value=provider))
    result = await billing.pending_checkout(db, row.user_id, reconcile_expiry=True)
    assert (result is row) is still_pending
    assert row.status == state
    provider.checkout_state.assert_awaited_once_with(row)


async def test_unknown_remote_creation_is_not_released_even_after_local_expiry(monkeypatch):
    db, stored, provider, user = checkout_fixture(monkeypatch)
    stored.append(SubscriptionCheckout(id=uuid.uuid4(), user_id=user.id, provider='stripe', plan_code='pro', interval='month',
        status='creating', expires_at=utcnow()-timedelta(days=2)))
    with pytest.raises(AppError) as error:
        await billing.start_checkout(db, user, 'pro', 'month')
    assert error.value.code == 'checkout_in_progress'
    assert stored[0].status == 'creating'
    provider.checkout.assert_not_called()


async def test_recovery_rejection_cannot_release_an_unknown_prior_remote_creation(monkeypatch):
    db, stored, provider, user = checkout_fixture(monkeypatch)
    stored.append(SubscriptionCheckout(id=uuid.uuid4(), user_id=user.id, provider='stripe', plan_code='pro', interval='month',
        status='creating', expires_at=utcnow()+timedelta(minutes=10)))
    # Provider validation may now reject an old requested expiry (<30 minutes)
    # even though the original uncertain call created an open session.
    provider.checkout.side_effect = httpx.HTTPStatusError('expiry no longer valid',
        request=httpx.Request('POST', 'https://checkout.example'), response=httpx.Response(400))
    provider.checkout.side_effect.status_code = 400
    with pytest.raises(AppError):
        await billing.start_checkout(db, user, 'pro', 'month')
    assert stored[0].status == 'creating'


async def test_stripe_checkout_has_stable_provider_idempotency_and_expiry():
    provider = billing.StripeProvider.__new__(billing.StripeProvider)
    provider.settings = SimpleNamespace(public_web_url='https://clastio.online', stripe_prices={})
    expires = utcnow()+timedelta(hours=1)
    create = AsyncMock(return_value=SimpleNamespace(id='cs_test', url='https://checkout.example', expires_at=int(expires.timestamp())))
    provider.client = SimpleNamespace(v1=SimpleNamespace(checkout=SimpleNamespace(sessions=SimpleNamespace(create_async=create))))
    row = SubscriptionCheckout(id=uuid.uuid4(), expires_at=expires)
    user = SimpleNamespace(id=uuid.uuid4(), email='teacher@example.com')
    plan = SimpleNamespace(code='pro', name='Pro', price_monthly_aed=249)
    for _ in range(2):
        result = await provider.checkout(user, plan, 'month', None, reservation=row)
        assert result.id == 'cs_test'
    first, retry = create.await_args_list
    assert first.kwargs == retry.kwargs
    assert first.kwargs['options']['idempotency_key'] == f'subscription-checkout:{row.id}'
    assert first.kwargs['params']['expires_at'] == int(expires.timestamp())
    assert first.kwargs['params']['metadata']['clastio_checkout_id'] == str(row.id)


@pytest.mark.parametrize('provider_name,state,cancellable', [('stripe', 'open', True), ('stripe', 'processing', False), ('dodo', 'open', False)])
async def test_explicit_checkout_cancel_only_releases_a_confirmed_unpaid_stripe_session(monkeypatch, provider_name, state, cancellable):
    db, stored, provider, user = checkout_fixture(monkeypatch, provider_name)
    row = SubscriptionCheckout(id=uuid.uuid4(), user_id=user.id, provider=provider_name, provider_session_id='test', status='open')
    stored.append(row)
    provider.checkout_state = AsyncMock(return_value=state)
    provider.expire_checkout = AsyncMock()
    if cancellable:
        await billing.cancel_pending_checkout(db, user.id)
        provider.expire_checkout.assert_awaited_once_with(row)
        assert row.status == 'expired'
    else:
        with pytest.raises(AppError) as error:
            await billing.cancel_pending_checkout(db, user.id)
        assert error.value.code == 'checkout_not_cancellable'
        provider.expire_checkout.assert_not_called()
        assert row.status == 'open'


async def test_lost_expiration_response_keeps_checkout_reserved(monkeypatch):
    db, stored, provider, user = checkout_fixture(monkeypatch)
    row = SubscriptionCheckout(id=uuid.uuid4(), user_id=user.id, provider='stripe', provider_session_id='test', status='open')
    stored.append(row)
    provider.checkout_state = AsyncMock(return_value='open')
    provider.expire_checkout = AsyncMock(side_effect=httpx.ReadTimeout('lost closure response'))
    with pytest.raises(AppError) as error:
        await billing.cancel_pending_checkout(db, user.id)
    assert error.value.code == 'checkout_reconciliation_unavailable'
    assert row.status == 'open'
    db.commit.assert_not_called()


async def test_dodo_payment_before_subscription_keeps_the_reservation(monkeypatch):
    settle = AsyncMock()
    monkeypatch.setattr(billing, 'settle_checkout', settle)
    monkeypatch.setattr(billing, '_find_sub', AsyncMock(return_value=None))
    monkeypatch.setattr(billing, 'get_setting', AsyncMock(return_value={}))
    monkeypatch.setattr(billing._SubChanges, 'apply', AsyncMock())
    await billing.handle_dodo_event(AsyncMock(), {'type': 'payment.succeeded', 'data': {
        'subscription_id': 'sub_test', 'metadata': {'clastio_checkout_id': str(uuid.uuid4())},
    }})
    assert settle.await_args.args[-1] == 'processing'
