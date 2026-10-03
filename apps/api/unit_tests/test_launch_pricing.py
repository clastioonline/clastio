from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.errors import AppError
from app.models import Plan
from app.services import billing


async def test_explicit_price_rollout_preserves_limits_and_is_idempotent():
    rows = {code: Plan(code=code, name=code, price_monthly_aed=old, price_annual_aed=old * 10,
                       limits={"credits": 123, "ai_images": 7}, features=["Custom feature"])
            for code, old in [("free", 0), ("teacher", 99), ("pro", 149), ("assistant", 249)]}
    db = AsyncMock()
    db.get.side_effect = lambda model, code: rows.get(code)
    assert await billing.update_launch_prices(db) == ["teacher", "pro", "assistant"]
    assert [(rows[c].price_monthly_aed, rows[c].price_annual_aed) for c in ("teacher", "pro", "assistant")] == [(149, 1490), (249, 2490), (399, 3990)]
    assert all(row.limits == {"credits": 123, "ai_images": 7} and row.features == ["Custom feature"] for row in rows.values())
    assert rows["free"].price_monthly_aed == 0
    assert await billing.update_launch_prices(db) == []
    db.execute.assert_not_called()
    db.add.assert_not_called()


@pytest.mark.parametrize("amount,currency,frequency,count,active", [
    (9900, "aed", "month", 1, True), (14900, "usd", "month", 1, True),
    (14900, "aed", "year", 1, True), (14900, "aed", "month", 2, True),
    (14900, "aed", "month", 1, False), (None, "aed", "month", 1, True),
])
def test_stale_or_incompatible_payment_price_is_rejected(amount, currency, frequency, count, active):
    with pytest.raises(AppError) as exc:
        billing._check_catalogue_price(SimpleNamespace(price_monthly_aed=149), "month", amount=amount,
                                      currency=currency, frequency=frequency, count=count, active=active)
    assert exc.value.code == "billing_price_mismatch"


async def test_stripe_stale_price_never_creates_checkout():
    provider = billing.StripeProvider.__new__(billing.StripeProvider)
    provider.settings = SimpleNamespace(public_web_url="https://clastio.online", stripe_prices={"teacher_monthly": "price_old"})
    create = AsyncMock()
    provider.client = SimpleNamespace(v1=SimpleNamespace(
        prices=SimpleNamespace(retrieve_async=AsyncMock(return_value=SimpleNamespace(unit_amount=9900, currency="aed", active=True,
            recurring=SimpleNamespace(interval="month", interval_count=1)))),
        checkout=SimpleNamespace(sessions=SimpleNamespace(create_async=create))))
    with pytest.raises(AppError):
        await provider.checkout(SimpleNamespace(id="teacher", email="teacher@example.com"),
                                SimpleNamespace(code="teacher", name="Teacher", price_monthly_aed=149), "month", None)
    create.assert_not_called()


async def test_dodo_stale_product_never_creates_checkout():
    provider = billing.DodoProvider.__new__(billing.DodoProvider)
    provider.products = {"teacher_month": "pdt_old"}
    provider.settings = SimpleNamespace(public_web_url="https://clastio.online")
    create = AsyncMock()
    provider.client = SimpleNamespace(products=SimpleNamespace(retrieve=AsyncMock(return_value=SimpleNamespace(
        price=SimpleNamespace(price=9900, currency="AED", type="recurring_price", payment_frequency_interval="month", payment_frequency_count=1)))),
        checkout_sessions=SimpleNamespace(create=create))
    with pytest.raises(AppError):
        await provider.checkout(SimpleNamespace(id="teacher", email="teacher@example.com", name="Teacher"),
                                SimpleNamespace(code="teacher", name="Teacher", price_monthly_aed=149), "month", None)
    create.assert_not_called()


def test_annual_price_and_decimal_minor_units():
    plan = SimpleNamespace(price_monthly_aed="149.99", price_annual_aed=1490)
    assert billing._plan_amount_minor(plan, "month") == 14999
    billing._check_catalogue_price(plan, "year", amount=149000, currency="AED", frequency="month", count=12)
