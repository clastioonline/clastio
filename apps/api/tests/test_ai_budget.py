"""Real database tests: concurrent admission, uncertain billing and bounded retries."""
import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.ai import budget
from app.ai.base import AIError, ChatMessage, TextResult, Usage
from app.ai.service import AIService, Route
from app.core.db import get_sessionmaker
from app.models import AICallReservation, AppSetting

CARD = {"input": 1, "output": 5, "cached": .1, "cache_write": 2, "ceiling_usd": .1,
        "source": "test-only synthetic rates"}


@pytest.fixture
async def paid_policy(database):
    async with get_sessionmaker()() as db:
        await db.execute(delete(AICallReservation))
        originals = (await db.execute(select(AppSetting).where(
            AppSetting.key.in_(["ai_budget", "ai_rate_cards"])))).scalars().all()
        saved = {r.key: r.value for r in originals}
        for row in originals:
            await db.delete(row)
        await db.flush()
        db.add(AppSetting(key="ai_budget", value={"live_enabled": True, "daily_usd": .2}))
        db.add(AppSetting(key="ai_rate_cards", value={"openai:test-model": CARD}))
        await db.commit()
    yield
    async with get_sessionmaker()() as db:
        await db.execute(delete(AICallReservation))
        await db.execute(delete(AppSetting).where(AppSetting.key.in_(["ai_budget", "ai_rate_cards"])))
        for k, v in saved.items():
            db.add(AppSetting(key=k, value=v))
        await db.commit()


async def reserve(**kwargs):
    return await budget.reserve(provider="openai", model="test-model", task="test", owner_id=None,
                                job_id=None, **kwargs)


async def test_concurrent_admission_cannot_overspend(paid_policy):
    results = await asyncio.gather(*(reserve() for _ in range(8)), return_exceptions=True)
    assert sum(not isinstance(r, Exception) for r in results) == 2
    assert sum(isinstance(r, budget.BudgetError) for r in results) == 6


async def test_settlement_releases_unused_hold_and_prices_cache_writes(paid_policy):
    ticket = await reserve()
    cost = await budget.settle(ticket, Usage(input_tokens=1000, output_tokens=1000,
                                           cached_tokens=1000, cache_write_tokens=1000, reasoning_tokens=500), False)
    assert cost == pytest.approx(.0081)  # Reasoning is included in output, never charged twice.
    assert await budget.settle(ticket, Usage(output_tokens=20000), True) == pytest.approx(cost)
    await reserve()
    async with get_sessionmaker()() as db:
        row = await db.get(AICallReservation, ticket)
        assert row.status == "settled" and not row.success
        assert row.usage["reasoning_tokens"] == 500


async def test_unknown_charge_remains_held_across_month_boundary(paid_policy):
    ticket = await reserve()
    await budget.settle(ticket, None, False)
    async with get_sessionmaker()() as db:
        row = await db.get(AICallReservation, ticket)
        row.created_at = datetime.now(UTC) - timedelta(days=40)
        await db.commit()
    await reserve()
    with pytest.raises(budget.BudgetError):
        await reserve()


async def test_limits_and_unapproved_models_block_before_call(paid_policy):
    with pytest.raises(budget.BudgetError, match="too large"):
        await reserve(output_tokens=64000)
    with pytest.raises(budget.BudgetError, match="approved price"):
        await budget.reserve(provider="openai", model="unapproved", task="test", owner_id=None, job_id=None)


async def test_underestimated_ceiling_pauses_live_calls(paid_policy):
    ticket = await reserve()
    assert await budget.settle(ticket, Usage(output_tokens=100000), True) == .5
    with pytest.raises(budget.BudgetError, match="paused"):
        await reserve()


async def test_uncertain_failure_not_retried(paid_policy, monkeypatch):
    service = AIService()
    calls = []

    class Fake:
        async def generate_text(self, model, req):
            calls.append(model)
            raise AIError("connection lost", retryable=True)

    async def routes(tier):
        return [Route("openai", "test-model"), Route("openai", "test-model")]

    service.providers["openai"] = Fake()
    monkeypatch.setattr(service, "routes", routes)
    with pytest.raises(AIError) as exc:
        await service.text(task="test", tier="fast", system="", messages=[ChatMessage("user", "Hi")])
    assert exc.value.retryable is False
    assert len(calls) == 1
    async with get_sessionmaker()() as db:
        row = (await db.execute(select(AICallReservation))).scalar_one()
        assert row.status == "uncertain" and row.charged_usd is None


async def test_failed_validation_is_billed_and_fallback_is_bounded(paid_policy, monkeypatch):
    service = AIService()
    calls = []

    class Fake:
        async def generate_text(self, model, req):
            calls.append(model)
            if len(calls) == 1:
                raise AIError("validation", usage=Usage(output_tokens=100))
            return TextResult("Ready", Usage(output_tokens=100), model, "openai")

    async def routes(tier):
        return [Route("openai", "test-model"), Route("openai", "test-model")]

    service.providers["openai"] = Fake()
    monkeypatch.setattr(service, "routes", routes)
    assert await service.text(task="test", tier="fast", system="", messages=[]) == "Ready"
    async with get_sessionmaker()() as db:
        rows = (await db.execute(select(AICallReservation))).scalars().all()
        assert len(rows) == 2
        assert sum(float(r.charged_usd) for r in rows) == pytest.approx(.001)


async def test_teacher_credit_estimate_uses_server_settings(client, teacher):
    response = await client.get("/api/v1/usage/estimates", headers=teacher["headers"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["costs"]["course_plan"] == 2
    assert body["remaining"] >= 0 and body["reset_at"]


@pytest.mark.parametrize("key", ["daily_usd", "monthly_usd", "user_monthly_usd", "call_usd"])
async def test_each_spending_scope_is_enforced(paid_policy, key):
    async with get_sessionmaker()() as db:
        row = await db.get(AppSetting, "ai_budget")
        row.value = {"live_enabled": True, key: .05}
        await db.commit()
    with pytest.raises(budget.BudgetError):
        await reserve()


async def test_job_context_and_limits_survive_worker_retry(paid_policy, teacher):
    import uuid

    from app.core.logging import job_id_var
    from app.models import GenerationJob

    async with get_sessionmaker()() as db:
        job = GenerationJob(type="test", owner_id=uuid.UUID(teacher["id"]), status="running",
                            started_at=datetime.now(UTC))
        db.add(job)
        await db.commit()
        job_id = job.id
    token = job_id_var.set(str(job_id))
    try:
        ticket = await reserve()
        async with get_sessionmaker()() as db:
            row = await db.get(AICallReservation, ticket)
            assert row.job_id == job_id and str(row.owner_id) == teacher["id"]
            job = await db.get(GenerationJob, job_id)
            job.started_at = datetime.now(UTC) + timedelta(seconds=1)
            await db.commit()
        with pytest.raises(budget.BudgetError, match="unconfirmed"):
            await reserve()
    finally:
        job_id_var.reset(token)


async def test_admin_controls_validation_and_reconciliation(client, teacher, paid_policy):
    from tests.conftest import make_staff

    admin = await make_staff(client, "super_admin")
    headers = admin["headers"]
    assert (await client.get("/api/v1/admin/ai-budget", headers=teacher["headers"])).status_code == 403
    invalid = await client.put("/api/v1/admin/settings/ai_budget", headers=headers, json={"monthly_usd": -1})
    assert invalid.status_code == 422
    invalid = await client.put("/api/v1/admin/settings/ai_rate_cards", headers=headers,
                               json={"openai:test-model": {"input": -1}})
    assert invalid.status_code == 422
    ticket = await reserve()
    await budget.settle(ticket, None, False)
    before = await client.get("/api/v1/admin/ai-budget", headers=headers)
    assert before.status_code == 200 and before.json()["held_usd"] == .1
    reconciled = await client.post(f"/api/v1/admin/ai-budget/{ticket}/reconcile", headers=headers,
                                  json={"amount_usd": .025, "reference": "invoice-test-request-123"})
    assert reconciled.status_code == 200, reconciled.text
    repeated = await client.post(f"/api/v1/admin/ai-budget/{ticket}/reconcile", headers=headers,
                                json={"amount_usd": 0, "reference": "invoice-test-request-123"})
    assert repeated.status_code == 409
    after = (await client.get("/api/v1/admin/ai-budget", headers=headers)).json()
    assert after["held_usd"] == 0 and after["spent_usd"] == .025


async def test_stream_without_final_usage_keeps_hold(paid_policy, monkeypatch):
    service = AIService()

    class Fake:
        async def stream_text(self, model, req, usage):
            yield "Partial answer"
            raise AIError("stream disconnected")

    async def routes(tier):
        return [Route("openai", "test-model")]

    service.providers["openai"] = Fake()
    monkeypatch.setattr(service, "routes", routes)
    received = []
    with pytest.raises(AIError):
        async for chunk in service.stream(task="test", tier="content", system="", messages=[]):
            received.append(chunk)
    assert received == ["Partial answer"]
    async with get_sessionmaker()() as db:
        row = (await db.execute(select(AICallReservation))).scalar_one()
        assert row.status == "uncertain" and row.usage_id is not None


async def test_cache_is_tenant_and_schema_specific(monkeypatch, teacher, client):
    import uuid

    from pydantic import BaseModel

    from app.ai.base import StructuredResult
    from tests.conftest import make_user

    other = await make_user(client)

    class Answer(BaseModel):
        text: str

    calls = []
    service = AIService()

    class Fake:
        async def generate_structured(self, model, req, schema):
            calls.append(req)
            return StructuredResult(Answer(text="Result"), Usage(), model, "offline")

    service.providers["offline"] = Fake()
    options = dict(task="cache-test", tier="fast", system="", prompt="Same", schema=Answer, cache=True)
    await service.structured(**options, owner_id=uuid.UUID(teacher["id"]))
    await service.structured(**options, owner_id=uuid.UUID(teacher["id"]))
    await service.structured(**options, owner_id=uuid.UUID(other["id"]))
    await service.structured(**options, owner_id=uuid.UUID(other["id"]), prompt_version="v2")
    assert len(calls) == 3


@pytest.mark.parametrize("setting", [{"job_usd": .05}, {"max_calls_per_job": 1}])
async def test_per_job_caps(paid_policy, setting):
    from app.models import GenerationJob

    async with get_sessionmaker()() as db:
        row = await db.get(AppSetting, "ai_budget")
        row.value = {"live_enabled": True, **setting}
        job = GenerationJob(type="test")
        db.add(job)
        await db.commit()
        job_id = job.id
    args = dict(provider="openai", model="test-model", task="test", owner_id=None, job_id=job_id)
    if "max_calls_per_job" in setting:
        ticket = await budget.reserve(**args)
        await budget.settle(ticket, Usage(output_tokens=1), True)
    with pytest.raises(budget.BudgetError):
        await budget.reserve(**args)
