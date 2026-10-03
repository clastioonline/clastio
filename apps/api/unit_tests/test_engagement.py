"""Limits and reward/payment boundaries without network or PostgreSQL."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.routes.platform import _validate_setting
from app.core.errors import AppError, LimitExceeded
from app.models import Plan
from app.services import billing, engagement, usage


async def test_trial_cap_does_not_change_paid_plan(monkeypatch):
    original = Plan(code='pro', name='Pro', limits={'credits': 500, 'ai_images': 100, 'whatsapp_messages': -1}, features=[],
                    price_monthly_aed=49, price_annual_aed=490)
    sub = SimpleNamespace(provider='trial', plan_code='pro')
    monkeypatch.setattr(usage, 'active_subscription', AsyncMock(return_value=sub))
    monkeypatch.setattr(usage, 'get_setting', AsyncMock(return_value={'credits': 50, 'ai_images': 5, 'whatsapp_messages': 20}))
    db = AsyncMock()
    db.get.return_value = original
    trial, _ = await usage.get_plan(db, SimpleNamespace(id=uuid.uuid4()))
    assert trial.limits == {'credits': 50, 'ai_images': 5, 'whatsapp_messages': 20}
    assert original.limits['credits'] == 500
    assert trial is not original


async def test_trial_checks_reserved_credits(monkeypatch):
    from datetime import UTC, datetime
    monkeypatch.setattr(usage, 'get_plan', AsyncMock(return_value=(SimpleNamespace(limits={'credits': 50}, name='Pro trial', code='pro'),
                                                                  SimpleNamespace(provider="trial", current_period_start=datetime.now(UTC)))))
    monkeypatch.setattr(usage, 'used', AsyncMock(return_value=40))
    monkeypatch.setattr(usage, 'reserved', AsyncMock(return_value=8))
    monkeypatch.setattr(usage, 'lock_user', AsyncMock())
    monkeypatch.setattr(usage, 'check_generation_allowed', AsyncMock())
    with pytest.raises(LimitExceeded):
        await usage.check(AsyncMock(), SimpleNamespace(id=uuid.uuid4(), role='teacher'), 'credits', 3)


@pytest.mark.parametrize('key,value', [('trial', {'credits': -1}), ('trial', {'ai_images': 'unlimited'}),
                                     ('referrals', {'reward_media_credits': 0}), ('referrals', {'enabled': 'yes'})])
def test_invalid_engagement_settings(key, value):
    with pytest.raises(AppError):
        _validate_setting(key, value)


async def test_referral_awarded_to_both_once(monkeypatch):
    referred = SimpleNamespace(id=uuid.uuid4(), referred_by_id=uuid.uuid4(), role='teacher', status='active', email_verified=True)
    referrer = SimpleNamespace(id=referred.referred_by_id, role='teacher', status='active')
    rows = []
    db = AsyncMock()
    db.add = rows.append
    db.get.side_effect = lambda model, key: referred if key == referred.id else referrer
    db.execute.return_value = SimpleNamespace(first=lambda: rows[0] if rows else None)
    monkeypatch.setattr(engagement, 'get_setting', AsyncMock(return_value={'enabled': True, 'reward_media_credits': 25}))
    send = AsyncMock()
    monkeypatch.setattr('app.services.notifications.send', send)
    assert await engagement.reward_referral(db, referred.id)
    assert not await engagement.reward_referral(db, referred.id)
    assert len(rows) == 2
    assert {r.owner_id for r in rows} == {referred.id, referrer.id}
    assert all(r.amount == 25 and r.resource == 'media_credits' for r in rows)
    assert send.await_count == 2


async def test_self_referrals_cannot_receive_rewards(monkeypatch):
    user = SimpleNamespace(id=uuid.uuid4(), role='teacher', status='active', email_verified=True)
    user.referred_by_id = user.id
    db = AsyncMock()
    db.get.return_value = user
    monkeypatch.setattr(engagement, 'get_setting', AsyncMock(return_value={'enabled': True, 'reward_media_credits': 25}))
    assert not await engagement.reward_referral(db, user.id)
    db.add.assert_not_called()


def stripe_provider():
    provider = billing.StripeProvider.__new__(billing.StripeProvider)
    provider.settings = SimpleNamespace(public_web_url='https://clastio.online', stripe_prices={})
    provider.client = SimpleNamespace(v1=SimpleNamespace(promotion_codes=SimpleNamespace(list_async=AsyncMock()),
        checkout=SimpleNamespace(sessions=SimpleNamespace(create_async=AsyncMock(return_value=SimpleNamespace(url='https://checkout.example'))))))
    return provider


async def test_stripe_coupon_does_not_conflict_with_promotion_field():
    provider = stripe_provider()
    provider.client.v1.promotion_codes.list_async.return_value = SimpleNamespace(data=[SimpleNamespace(id='promo_123')])
    await provider.checkout(SimpleNamespace(id=uuid.uuid4(), email='teacher@example.com'),
                            SimpleNamespace(code='pro', name='Pro', price_monthly_aed=49), 'month', None, 'SAVE20')
    params = provider.client.v1.checkout.sessions.create_async.call_args.kwargs['params']
    assert params['discounts'] == [{'promotion_code': 'promo_123'}]
    assert 'allow_promotion_codes' not in params


async def test_invalid_coupon_never_creates_checkout():
    provider = stripe_provider()
    provider.client.v1.promotion_codes.list_async.return_value = SimpleNamespace(data=[])
    with pytest.raises(AppError) as exc:
        await provider.checkout(SimpleNamespace(id=uuid.uuid4(), email='teacher@example.com'),
                                SimpleNamespace(code='pro', name='Pro', price_monthly_aed=49), 'month', None, 'EXPIRED')
    assert exc.value.code == 'invalid_coupon'
    provider.client.v1.checkout.sessions.create_async.assert_not_called()


async def test_dodo_coupon_forwarded_to_gateway():
    provider = billing.DodoProvider.__new__(billing.DodoProvider)
    provider.settings = SimpleNamespace(public_web_url='https://clastio.online')
    provider.products = {'pro_month': 'pdt_pro'}
    provider.client = SimpleNamespace(checkout_sessions=SimpleNamespace(create=AsyncMock(return_value=SimpleNamespace(checkout_url='https://checkout.example'))))
    await provider.checkout(SimpleNamespace(id=uuid.uuid4(), email='teacher@example.com', name='Teacher'),
                            SimpleNamespace(code='pro', name='Pro'), 'month', None, 'SAVE20')
    assert provider.client.checkout_sessions.create.call_args.kwargs['discount_codes'] == ['SAVE20']
