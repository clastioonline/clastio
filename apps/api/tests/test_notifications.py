"""Notification catalog, reminders (trial, renewal, dunning, expiring grants), job notices, receipts, staff alerts,
preferences and announcement broadcasts."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select, update

from app.core.db import get_sessionmaker, utcnow
from app.models import EmailOutbox, Notification, Subscription
from tests.conftest import make_staff, make_user
from tests.test_media_and_dodo import dodo_post


async def _titles(uid: str) -> list[str]:
    async with get_sessionmaker()() as db:
        return [n.title for n in (await db.execute(select(Notification).where(
            Notification.user_id == uuid.UUID(uid)))).scalars().all()]


async def _emails(uid: str) -> list[str]:
    async with get_sessionmaker()() as db:
        return [e.template for e in (await db.execute(select(EmailOutbox).where(
            EmailOutbox.user_id == uuid.UUID(uid)))).scalars().all()]


async def test_trial_ending_reminder_is_sent_once(client):
    from app.services.notifications import run_reminders

    u = await make_user(client, plan="trial")
    async with get_sessionmaker()() as db:
        await db.execute(update(Subscription).where(Subscription.user_id == uuid.UUID(u["id"]),
                                                    Subscription.provider == "trial")
                         .values(current_period_end=utcnow() + timedelta(days=2, hours=12)))
        await db.commit()
    await run_reminders()
    await run_reminders()
    titles = await _titles(u["id"])
    assert titles.count("Your trial ends in 3 days") == 1
    assert (await _emails(u["id"])).count("trial_ending") == 1


async def test_renewal_reminder_and_dunning(client):
    from app.services.notifications import run_reminders

    u = await make_user(client, plan="free")
    uid = uuid.UUID(u["id"])
    async with get_sessionmaker()() as db:
        db.add(Subscription(user_id=uid, plan_code="pro", status="active", provider="dodo", interval="month",
                            provider_subscription_id=f"sub_{uuid.uuid4().hex[:8]}",
                            current_period_end=utcnow() + timedelta(days=2)))
        await db.commit()
    await run_reminders()
    assert any(t.startswith("Your Teacher Pro plan renews on") for t in await _titles(u["id"]))
    assert "renewal_upcoming" in await _emails(u["id"])

    async with get_sessionmaker()() as db:  # the renewal then fails and stays unpaid for 4 days
        await db.execute(update(Subscription).where(Subscription.user_id == uid, Subscription.provider == "dodo")
                         .values(status="past_due", updated_at=utcnow() - timedelta(days=4)))
        await db.commit()
    await run_reminders()
    await run_reminders()
    assert (await _titles(u["id"])).count("Your payment is still outstanding") == 1
    assert "payment_reminder" in await _emails(u["id"])


async def test_expiring_granted_plan_reminder(client):
    from app.services.notifications import run_reminders

    u = await make_user(client, plan="assistant")  # staff-granted for one month
    async with get_sessionmaker()() as db:
        await db.execute(update(Subscription).where(Subscription.user_id == uuid.UUID(u["id"]),
                                                    Subscription.provider == "manual")
                         .values(current_period_end=utcnow() + timedelta(days=5)))
        await db.commit()
    await run_reminders()
    assert any("access ends on" in t for t in await _titles(u["id"]))


async def test_lesson_ready_notice(client):
    u = await make_user(client)
    r = await client.post("/api/v1/courses", headers=u["headers"], json={
        "topic": "Volcanoes", "grade": "6", "subject": "Science", "num_lectures": 1, "slides_per_lecture": 6,
        "auto_generate": True})
    assert r.status_code == 200
    titles = await _titles(u["id"])
    assert "Unit planned: Volcanoes" in titles and any(t.startswith("Lesson ready:") for t in titles)


async def test_payment_receipt_and_staff_alert_on_failure(client):
    staff = await make_staff(client, "finance")
    u = await make_user(client, plan="free")
    pay = {"payment_id": f"pay_{uuid.uuid4().hex[:8]}", "total_amount": 5900, "currency": "AED",
           "metadata": {"user_id": u["id"], "kind": "media_pack", "pack_code": "creator"}}
    await dodo_post(client, {"type": "payment.succeeded", "data": pay})
    assert "Payment received: AED 59.00" in await _titles(u["id"])
    failed = {"payment_id": f"pay_{uuid.uuid4().hex[:8]}", "total_amount": 9900, "currency": "AED",
              "error_message": "Insufficient funds", "metadata": {"user_id": u["id"]}}
    await dodo_post(client, {"type": "payment.failed", "data": failed})
    assert any(t == f"Payment failed: {u['email']}" for t in await _titles(staff["id"]))


async def test_new_ticket_alerts_support_staff_only(client):
    support = await make_staff(client, "support")
    analyst = await make_staff(client, "analyst")
    u = await make_user(client)
    await client.post("/api/v1/support/tickets", headers=u["headers"],
                      json={"kind": "billing", "subject": "Charged twice", "body": "I see two charges this month."})
    assert any("billing request" in t for t in await _titles(support["id"]))
    assert not any("request #" in t for t in await _titles(analyst["id"]))


async def test_preferences_mute_optional_but_not_mandatory(client):
    from app.services.notifications import send

    u = await make_user(client)
    prefs = (await client.get("/api/v1/me/notification-preferences", headers=u["headers"])).json()["items"]
    assert next(p for p in prefs if p["category"] == "security")["mandatory"] is True
    r = await client.put("/api/v1/me/notification-preferences", headers=u["headers"], json={"categories": {
        "billing": {"email": False}, "billing_alert": {"email": False, "in_app": False}}})
    items = {p["category"]: p for p in r.json()["items"]}
    assert items["billing"]["email"] is False and items["billing_alert"]["email"] is True  # mandatory stays on

    from app.models import User

    async with get_sessionmaker()() as db:
        user = await db.get(User, uuid.UUID(u["id"]))
        await send(db, user, "renewal_upcoming", dedupe_key="t1", plan="Pro", date="1 Jan", amount="AED 149")
        await send(db, user, "payment_retry_reminder", dedupe_key="t2", plan="Pro", days=3)
        await db.commit()
    mails = await _emails(u["id"])
    assert "renewal_upcoming" not in mails and "payment_reminder" in mails


async def test_notification_delete_is_owner_only(client):
    from app.services.notify import notify

    a = await make_user(client)
    b = await make_user(client)
    async with get_sessionmaker()() as db:
        await notify(db, uuid.UUID(a["id"]), "system", "Mine")
        await db.commit()
    nid = (await client.get("/api/v1/me/notifications", headers=a["headers"])).json()["items"][0]["id"]
    assert (await client.delete(f"/api/v1/me/notifications/{nid}", headers=b["headers"])).status_code == 404
    assert (await client.delete(f"/api/v1/me/notifications/{nid}", headers=a["headers"])).status_code == 200


async def test_announcement_broadcast(client):
    admin = await make_staff(client, "admin")
    u = await make_user(client)
    title = f"New: Arabic slides {uuid.uuid4().hex[:4]}"
    r = await client.post("/api/v1/admin/announcements", headers=admin["headers"],
                          json={"kind": "feature", "title": title, "audience": "teachers", "notify_users": True})
    assert r.status_code == 200
    assert title in await _titles(u["id"])
    assert title not in await _titles(admin["id"])  # teachers-only
