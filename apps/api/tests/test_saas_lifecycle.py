from __future__ import annotations

import uuid

from tests.conftest import make_user, start_trial_for_user


async def _signup(client, email=None):
    email = email or f"t-{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-1", "name": "New Teacher",
                                                        "accept_terms": True})
    assert r.status_code == 200, r.text
    client.cookies.clear()
    return r.json(), {"Authorization": f"Bearer {r.json()['token']}"}


async def test_new_teacher_chooses_verified_no_card_trial_that_ends_on_free(client):
    data, h = await _signup(client)
    assert data["user"]["onboarding_completed"] is False
    usage = (await client.get("/api/v1/me/usage", headers=h)).json()
    assert usage["plan"]["code"] == "free" and usage["trial"] is None
    assert (await client.post("/api/v1/auth/trial", headers=h)).status_code == 403
    await start_trial_for_user(client, data["user"]["id"], data["user"]["email"], h)
    usage = (await client.get("/api/v1/me/usage", headers=h)).json()
    assert usage["plan"]["code"] == "pro" and usage["trial"]["active"] and usage["trial"]["days_left"] == 7
    assert usage["subscription"]["provider"] == "trial"

    from sqlalchemy import update

    from app.core.db import get_sessionmaker, utcnow
    from app.models import Subscription

    async with get_sessionmaker()() as db:  # the trial runs out
        await db.execute(update(Subscription).where(Subscription.user_id == uuid.UUID(data["user"]["id"]))
                         .values(current_period_end=utcnow()))
        await db.commit()
    usage = (await client.get("/api/v1/me/usage", headers=h)).json()
    assert usage["plan"]["code"] == "free" and usage["trial"] == {"active": False, "ended": True}
    # Free-plan limits apply again: at most 3 lessons per unit.
    r = await client.post("/api/v1/courses", headers=h, json={"topic": "Magnets", "grade": "5", "subject": "Science",
                                                              "num_lectures": 5, "slides_per_lecture": 8})
    assert r.status_code == 402 and r.json()["error"]["code"] == "limit_exceeded"


async def test_admin_can_turn_the_trial_off(client):
    from tests.test_media_and_dodo import make_admin

    admin = await make_admin(client)
    r = await client.put("/api/v1/admin/settings/trial", headers=admin["headers"], json={"enabled": False, "plan": "pro", "days": 7})
    assert r.status_code == 200
    try:
        _, h = await _signup(client)
        assert (await client.get("/api/v1/me/usage", headers=h)).json()["plan"]["code"] == "free"
        assert (await client.put("/api/v1/admin/settings/trial", headers=admin["headers"],
                                 json={"enabled": True, "plan": "gold", "days": 7})).status_code == 422
    finally:
        await client.put("/api/v1/admin/settings/trial", headers=admin["headers"], json={"enabled": True, "plan": "pro", "days": 7})


async def test_admins_are_not_customers(client):
    from tests.test_media_and_dodo import make_admin

    admin = await make_admin(client)
    me = (await client.get("/api/v1/auth/me", headers=admin["headers"])).json()["user"]
    assert me["role"] == "admin" and me["onboarding_completed"] is True
    before = (await client.get("/api/v1/admin/metrics", headers=admin["headers"])).json()
    await make_admin(client)  # another admin: not a teacher, not a sign-up
    granted = await make_user(client, plan="assistant")  # admin-granted plan: no revenue
    after = (await client.get("/api/v1/admin/metrics", headers=admin["headers"])).json()
    assert after["users"]["total"] == before["users"]["total"] + 1  # the new admin is not counted as a teacher
    assert after["revenue"]["mrr_aed"] == before["revenue"]["mrr_aed"]
    assert after["users"]["granted"] == before["users"]["granted"] + 1
    assert all(u["role"] == "teacher" for u in after["recent_signups"])
    assert any(u["email"] == granted["email"] for u in after["recent_signups"])


async def test_admin_extends_trial_but_never_overrides_a_paid_plan(client):
    from tests.test_media_and_dodo import make_admin

    admin = await make_admin(client)
    data, h = await _signup(client)
    uid = data["user"]["id"]
    await start_trial_for_user(client, uid, data["user"]["email"], h)
    r = await client.post(f"/api/v1/admin/users/{uid}/plan", headers=admin["headers"],
                          json={"extend_trial_days": 7, "reason": "Asked for more time"})
    assert r.status_code == 200
    assert (await client.get("/api/v1/me/usage", headers=h)).json()["trial"]["days_left"] == 14

    from app.core.db import get_sessionmaker
    from app.models import Subscription

    async with get_sessionmaker()() as db:  # the teacher then subscribes through the gateway
        db.add(Subscription(user_id=uuid.UUID(uid), plan_code="teacher", status="active", provider="dodo",
                            provider_subscription_id=f"sub_{uuid.uuid4().hex[:8]}"))
        await db.commit()
    r = await client.post(f"/api/v1/admin/users/{uid}/plan", headers=admin["headers"],
                          json={"plan": "assistant", "reason": "Upgrade request"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "paid_subscription"
