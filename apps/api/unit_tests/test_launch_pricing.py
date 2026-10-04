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


@pytest.mark.parametrize("overrides,is_recurring", [
    ({"price": 5900}, False), ({"price": None}, False), ({"currency": "USD"}, False),
    ({"type": "recurring_price"}, True), ({}, True), ({"pay_what_you_want": True}, False),
])
async def test_dodo_wrong_one_time_product_never_creates_checkout(overrides, is_recurring):
    provider = billing.DodoProvider.__new__(billing.DodoProvider)
    provider.settings = SimpleNamespace(public_web_url="https://clastio.online")
    create = AsyncMock()
    price = dict(price=1900, currency="AED", type="one_time_price", pay_what_you_want=False) | overrides
    provider.client = SimpleNamespace(products=SimpleNamespace(retrieve=AsyncMock(return_value=SimpleNamespace(
        is_recurring=is_recurring, price=SimpleNamespace(**price)))), checkout_sessions=SimpleNamespace(create=create))
    with pytest.raises(AppError) as error:
        await provider.checkout_one_time(SimpleNamespace(id="teacher", email="teacher@example.com", name="Teacher"),
            name="Starter", amount_aed=19, product_id="pdt_wrong", metadata={"kind": "media_pack", "pack_code": "starter"})
    assert error.value.code == "billing_price_mismatch"
    create.assert_not_called()


async def test_dodo_matching_one_time_pack_preserves_metadata_and_decimal_price():
    provider = billing.DodoProvider.__new__(billing.DodoProvider)
    provider.settings = SimpleNamespace(public_web_url="https://clastio.online")
    create = AsyncMock(return_value=SimpleNamespace(checkout_url="https://checkout.example/pack"))
    provider.client = SimpleNamespace(products=SimpleNamespace(retrieve=AsyncMock(return_value=SimpleNamespace(
        is_recurring=False, price=SimpleNamespace(price=1999, currency="aed", type="one_time_price")))),
        checkout_sessions=SimpleNamespace(create=create))
    url = await provider.checkout_one_time(SimpleNamespace(id="teacher", email="teacher@example.com", name="Teacher"),
        name="Starter", amount_aed=19.99, product_id="pdt_starter", metadata={"kind": "media_pack", "pack_code": "starter"})
    assert url == "https://checkout.example/pack"
    assert create.await_args.kwargs["product_cart"] == [{"product_id": "pdt_starter", "quantity": 1}]
    assert create.await_args.kwargs["metadata"] == {"user_id": "teacher", "kind": "media_pack", "pack_code": "starter"}


async def test_stripe_one_time_decimal_price_uses_exact_minor_units():
    provider = billing.StripeProvider.__new__(billing.StripeProvider)
    provider.settings = SimpleNamespace(public_web_url="https://clastio.online")
    create = AsyncMock(return_value=SimpleNamespace(url="https://checkout.example/pack"))
    provider.client = SimpleNamespace(v1=SimpleNamespace(checkout=SimpleNamespace(sessions=SimpleNamespace(create_async=create))))
    await provider.checkout_one_time(SimpleNamespace(id="teacher", email="teacher@example.com"), name="Starter",
        amount_aed=19.99, product_id=None, metadata={"kind": "media_pack", "pack_code": "starter"})
    params = create.await_args.kwargs["params"]
    assert params["line_items"][0]["price_data"]["unit_amount"] == 1999
