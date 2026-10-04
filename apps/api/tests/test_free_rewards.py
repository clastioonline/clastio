"""Real transaction tests for trial browser claims and reviewed reward credits."""
import asyncio
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.core.db import get_sessionmaker, utcnow
from app.models import CreditLedger, Payment, RewardSubmission, Subscription, TrialGrant, User
from app.services.settings import DEFAULTS, set_setting
from app.services.trial_device import COOKIE
from tests.conftest import make_staff, make_user


@pytest.fixture(scope="session")
async def seeded(database):
    # These transaction tests need plans and legal prerequisites, not slide previews.
    from app.seed import seed_plans
    from app.services import legal

    async with get_sessionmaker()() as db:
        await seed_plans(db)
        await legal.seed_documents(db)
        await db.commit()
    return True


@pytest.fixture(autouse=True)
async def rewards_program(seeded):
    await set_setting("rewards", dict(DEFAULTS["rewards"]))
    yield
    await set_setting("rewards", dict(DEFAULTS["rewards"]))


async def verified_teacher(client, plan=None):
    user = await make_user(client, plan=plan)
    async with get_sessionmaker()() as db:
        row = await db.get(User, uuid.UUID(user["id"]))
        row.email_verified = True
        await db.commit()
    return user


async def program_and_task(client, staff, *, credits=5, published=True, daily=20):
    program = {**DEFAULTS["rewards"], "enabled": True, "daily_credits": daily, "reason": "Test reward program"}
    response = await client.put("/api/v1/admin/rewards/program", headers=staff["headers"], json=program)
    assert response.status_code == 200, response.text
    response = await client.post("/api/v1/admin/rewards/tasks", headers=staff["headers"], json={
        "title": "Review lesson quality", "instructions": "Describe any confusing teaching examples in your own lesson.",
        "credits": credits, "published": published, "policy_acknowledged": True})
    assert response.status_code == 200, response.text
    return response.json()


async def submit_task(client, teacher, task, *, cookie=None):
    headers = dict(teacher["headers"])
    if cookie:
        headers["Cookie"] = f"{COOKIE}={cookie}"
    return await client.post(f"/api/v1/rewards/tasks/{task['id']}/submit", headers=headers,
                             json={"proof": "I checked my lesson and found the example needs a simpler explanation."})


async def approve(client, staff, submission):
    return await client.post(f"/api/v1/admin/rewards/submissions/{submission['id']}/review",
                             headers=staff["headers"], json={"approve": True, "note": "Verified useful quality feedback"})


async def test_trial_same_browser_block_and_narrow_shared_device_exception(client):
    first, second = await verified_teacher(client), await verified_teacher(client)
    staff = await make_staff(client)
    await client.get("/api/v1/auth/me", headers=first["headers"])
    cookie = client.cookies.get(COOKIE)
    assert cookie
    same_browser_first = {**first["headers"], "Cookie": f"{COOKIE}={cookie}"}
    same_browser_second = {**second["headers"], "Cookie": f"{COOKIE}={cookie}"}
    assert (await client.post("/api/v1/auth/trial", headers=same_browser_first)).status_code == 200
    blocked = await client.post("/api/v1/auth/trial", headers=same_browser_second)
    assert blocked.status_code == 409
    eligibility = await client.get("/api/v1/billing/subscription", headers=same_browser_second)
    assert eligibility.json()["trial_available"] is False
    allowed = await client.post("/api/v1/admin/rewards/trial-exception", headers=staff["headers"],
                                json={"email": second["email"], "reason": "Verified teachers sharing their school computer"})
    assert allowed.status_code == 200, allowed.text
    assert (await client.post("/api/v1/auth/trial", headers=same_browser_second)).status_code == 200
    # The support exception cannot reset the email trial grant.
    assert (await client.post("/api/v1/auth/trial", headers=same_browser_second)).status_code == 409
    assert (await client.post("/api/v1/admin/rewards/trial-exception", headers=staff["headers"],
        json={"email": second["email"], "reason": "This should not reset their previous trial"})).status_code == 409
    async with get_sessionmaker()() as db:
        assert (await db.execute(select(func.count()).select_from(TrialGrant).where(TrialGrant.user_id == uuid.UUID(second["id"])))).scalar_one() == 1


async def test_cookie_tampering_cannot_reset_trial_and_free_signin_remains_available(client):
    teacher = await verified_teacher(client)
    await client.get("/api/v1/auth/me", headers=teacher["headers"])
    cookie = client.cookies.get(COOKIE)
    headers = {**teacher["headers"], "Cookie": f"{COOKIE}={cookie[:-1]}x"}
    # This is still an authenticated account, but the changed installation is not trusted.
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 200
    blocked = await client.post("/api/v1/auth/trial", headers=headers)
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "browser_verification_failed"


async def test_expired_trial_falls_back_to_free_without_charge_or_monthly_refill(client):
    teacher = await verified_teacher(client)
    assert (await client.post("/api/v1/auth/trial", headers=teacher["headers"])).status_code == 200
    async with get_sessionmaker()() as db:
        sub = (await db.execute(select(Subscription).where(Subscription.user_id == uuid.UUID(teacher["id"]), Subscription.provider == "trial"))).scalars().one()
        sub.current_period_end = utcnow() - timedelta(seconds=1)
        db.add(CreditLedger(owner_id=uuid.UUID(teacher["id"]), amount=-30, resource="credits", reason="lesson_generation"))
        await db.commit()
    summary = (await client.get("/api/v1/me/usage", headers=teacher["headers"])).json()
    assert summary["plan"]["code"] == "free" and summary["trial"]["ended"] is True
    assert summary["usage"]["credits"]["available"] == summary["usage"]["credits"]["limit"] - 30
    async with get_sessionmaker()() as db:
        assert (await db.execute(select(func.count()).select_from(Payment).where(Payment.user_id == uuid.UUID(teacher["id"])))) .scalar_one() == 0


async def test_rewards_initially_empty_and_unpublished_task_cannot_be_submitted(client):
    teacher, staff = await verified_teacher(client), await make_staff(client)
    initial = (await client.get("/api/v1/rewards", headers=teacher["headers"])).json()
    assert not initial["enabled"] and initial["tasks"] == []
    task = await program_and_task(client, staff, published=False)
    assert (await submit_task(client, teacher, task)).status_code == 409


async def test_reward_review_concurrency_awards_once_and_increases_available_balance(client):
    teacher, staff = await verified_teacher(client), await make_staff(client)
    task = await program_and_task(client, staff)
    before = (await client.get("/api/v1/me/usage", headers=teacher["headers"])).json()["usage"]["credits"]["available"]
    submitted = await submit_task(client, teacher, task)
    assert submitted.status_code == 200, submitted.text
    outcomes = await asyncio.gather(approve(client, staff, submitted.json()), approve(client, staff, submitted.json()))
    assert sorted(response.status_code for response in outcomes) == [200, 409]
    after = (await client.get("/api/v1/me/usage", headers=teacher["headers"])).json()["usage"]["credits"]["available"]
    assert after == before + 5
    async with get_sessionmaker()() as db:
        entries = (await db.execute(select(CreditLedger).where(CreditLedger.owner_id == uuid.UUID(teacher["id"]), CreditLedger.reason == "task_reward"))).scalars().all()
        assert len(entries) == 1 and entries[0].amount == 5
        row = await db.get(RewardSubmission, uuid.UUID(submitted.json()["id"]))
        assert row.expires_at.day == 1 and row.expires_at > utcnow()
    assert (await submit_task(client, teacher, task)).status_code == 409


async def test_paid_trial_unverified_and_staff_accounts_cannot_earn_rewards(client):
    staff = await make_staff(client)
    task = await program_and_task(client, staff)
    paid = await verified_teacher(client, plan="pro")
    trial = await verified_teacher(client)
    assert (await client.post("/api/v1/auth/trial", headers=trial["headers"])).status_code == 200
    unverified = await make_user(client, plan=None)
    for account in (paid, trial, unverified, staff):
        assert (await submit_task(client, account, task)).status_code == 403


async def test_reward_browser_claim_prevents_other_email_repeating_task(client):
    first, second, staff = await verified_teacher(client), await verified_teacher(client), await make_staff(client)
    task = await program_and_task(client, staff)
    await client.get("/api/v1/auth/me", headers=first["headers"])
    cookie = client.cookies.get(COOKIE)
    response = await submit_task(client, first, task, cookie=cookie)
    assert response.status_code == 200, response.text
    assert (await approve(client, staff, response.json())).status_code == 200
    repeated = await submit_task(client, second, task, cookie=cookie)
    assert repeated.status_code == 409


async def test_reward_budget_and_permissions_fail_closed(client):
    teacher, staff, support = await verified_teacher(client), await make_staff(client), await make_staff(client, "support")
    task = await program_and_task(client, staff, credits=5, daily=4)
    response = await submit_task(client, teacher, task)
    assert response.status_code == 200
    assert (await approve(client, support, response.json())).status_code == 403
    limited = await approve(client, staff, response.json())
    assert limited.status_code == 409 and limited.json()["error"]["code"] == "reward_budget_reached"
    bypass = await client.put("/api/v1/admin/settings/rewards", headers=staff["headers"], json={"daily_credits": 1000000})
    assert bypass.status_code == 400


@pytest.mark.parametrize("budget", ["monthly_credits", "lifetime_credits", "global_daily_credits"])
async def test_reward_other_budget_caps(budget, client):
    teacher, staff = await verified_teacher(client), await make_staff(client)
    task = await program_and_task(client, staff)
    cfg = {**DEFAULTS["rewards"], "enabled": True, budget: 4, "reason": "Test bounded reward program"}
    assert (await client.put("/api/v1/admin/rewards/program", headers=staff["headers"], json=cfg)).status_code == 200
    response = await submit_task(client, teacher, task)
    assert response.status_code == 200
    rejected = await approve(client, staff, response.json())
    assert rejected.status_code == 409 and rejected.json()["error"]["code"] == "reward_budget_reached"


async def test_reward_approval_rechecks_expired_task(client):
    from app.models import RewardTask

    teacher, staff = await verified_teacher(client), await make_staff(client)
    task = await program_and_task(client, staff)
    submitted = await submit_task(client, teacher, task)
    assert submitted.status_code == 200
    async with get_sessionmaker()() as db:
        row = await db.get(RewardTask, uuid.UUID(task["id"]))
        row.ends_at = utcnow() - timedelta(seconds=1)
        await db.commit()
    reviewed = await approve(client, staff, submitted.json())
    assert reviewed.status_code == 409 and reviewed.json()["error"]["code"] == "reward_task_unavailable"


@pytest.mark.parametrize("changed,expected", [({"enabled": False}, "reward_task_unavailable"),
                                             ({"daily_credits": 4}, "reward_budget_reached")])
async def test_reward_approval_uses_persisted_program_despite_stale_process_config(client, monkeypatch, changed, expected):
    from app.services import settings

    teacher, staff = await verified_teacher(client), await make_staff(client)
    task = await program_and_task(client, staff)
    submitted = await submit_task(client, teacher, task)
    assert submitted.status_code == 200
    await set_setting("rewards", {**DEFAULTS["rewards"], "enabled": True, **changed})
    original = settings.get_setting

    async def stale(key):
        return {**DEFAULTS["rewards"], "enabled": True} if key == "rewards" else await original(key)

    monkeypatch.setattr(settings, "get_setting", stale)
    reviewed = await approve(client, staff, submitted.json())
    assert reviewed.status_code == 409 and reviewed.json()["error"]["code"] == expected


async def test_reward_approval_rechecks_task_and_current_plan(client):
    teacher, staff = await verified_teacher(client), await make_staff(client)
    task = await program_and_task(client, staff)
    response = await submit_task(client, teacher, task)
    assert response.status_code == 200
    from app.services.billing import set_manual_plan
    async with get_sessionmaker()() as db:
        await set_manual_plan(db, uuid.UUID(teacher["id"]), "pro", months=1)
    reviewed = await approve(client, staff, response.json())
    assert reviewed.status_code == 409 and reviewed.json()["error"]["code"] == "reward_ineligible"
