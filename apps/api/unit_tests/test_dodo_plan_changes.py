"""Signed current products control portal plan changes; no gateway or database access."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models import Plan, Subscription
from app.services import billing, usage


@pytest.mark.parametrize("original,selected,interval", [
    ("teacher", "pro", "month"),
    ("pro", "teacher", "month"),
    ("teacher", "pro", "year"),
])
async def test_current_product_overrides_original_checkout_metadata(monkeypatch, original, selected, interval):
    sub = Subscription(id=uuid.uuid4(), user_id=uuid.uuid4(), provider="dodo",
                       provider_subscription_id="sub_synthetic", plan_code=original, interval="month", status="active")
    plan = Plan(code=selected, name=selected, limits={"credits": 2000 if selected == "pro" else 800})
    db = AsyncMock()
    db.get.return_value = plan
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [sub]))
    monkeypatch.setattr(billing, "_find_sub", AsyncMock(return_value=sub))
    monkeypatch.setattr(billing, "get_setting", AsyncMock(return_value={"dodo_products": {f"{selected}_{interval}": "pdt_current"}}))
    monkeypatch.setattr(billing, "settle_checkout", AsyncMock())
    monkeypatch.setattr(billing._SubChanges, "apply", AsyncMock())
    await billing.handle_dodo_event(db, {"type": "subscription.plan_changed", "data": {
        "subscription_id": "sub_synthetic", "product_id": "pdt_current", "status": "active",
        "metadata": {"user_id": str(sub.user_id), "plan_code": original, "interval": "month"},
    }})
    assert sub.plan_code == selected
    assert sub.interval == interval
    db.get.assert_awaited_once_with(Plan, selected)
    monkeypatch.setattr(usage, "active_subscription", AsyncMock(return_value=sub))
    current_plan, _ = await usage.get_plan(db, SimpleNamespace(id=sub.user_id))
    assert current_plan.code == selected
    assert current_plan.limits["credits"] == (2000 if selected == "pro" else 800)


async def test_product_mapping_does_not_activate_an_unpaid_subscription(monkeypatch):
    sub = Subscription(id=uuid.uuid4(), user_id=uuid.uuid4(), provider="dodo", plan_code="teacher", status="pending")
    db = AsyncMock()
    db.get.return_value = Plan(code="pro", name="Pro")
    monkeypatch.setattr(billing, "_find_sub", AsyncMock(return_value=sub))
    monkeypatch.setattr(billing, "get_setting", AsyncMock(return_value={"dodo_products": {"pro_year": "pdt_current"}}))
    monkeypatch.setattr(billing._SubChanges, "apply", AsyncMock())
    await billing.handle_dodo_event(db, {"type": "subscription.updated", "data": {
        "subscription_id": "sub_synthetic", "product_id": "pdt_current", "status": "pending",
        "metadata": {"plan_code": "teacher", "interval": "month"},
    }})
    assert sub.plan_code == "pro" and sub.interval == "year"
    assert sub.status not in usage.ACTIVE_STATUSES


@pytest.mark.parametrize("mapping", [{}, {"missing_year": "pdt_current"}, {"pro_week": "pdt_current"}])
async def test_unmapped_or_invalid_product_keeps_the_existing_known_plan(monkeypatch, mapping):
    sub = Subscription(id=uuid.uuid4(), user_id=uuid.uuid4(), provider="dodo", plan_code="teacher", interval="month", status="pending")
    db = AsyncMock()
    db.get.return_value = None
    monkeypatch.setattr(billing, "_find_sub", AsyncMock(return_value=sub))
    monkeypatch.setattr(billing, "get_setting", AsyncMock(return_value={"dodo_products": mapping}))
    monkeypatch.setattr(billing._SubChanges, "apply", AsyncMock())
    await billing.handle_dodo_event(db, {"type": "subscription.updated", "data": {
        "subscription_id": "sub_synthetic", "product_id": "pdt_current", "status": "pending", "metadata": {},
    }})
    assert sub.plan_code == "teacher" and sub.interval == "month"
    assert sub.status == "pending"
