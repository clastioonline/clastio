"""Legal versioning and consent, notifications, usage warnings, support tickets, announcements, webhooks."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.models import AnalyticsEvent, EmailOutbox, Notification, Payment, SecurityEvent, WebhookEvent
from tests.conftest import make_staff, make_user
from tests.test_media_and_dodo import dodo_post

# --------------------------------------------------------------------------- legal


async def test_public_legal_pages(client):
    idx = (await client.get("/api/v1/legal")).json()["items"]
    assert {"terms", "privacy", "acceptable_use", "cookie", "refund"} <= {d["type"] for d in idx}
    terms = (await client.get("/api/v1/legal/terms")).json()
    assert terms["version"] and "requires review by a qualified lawyer" in terms["content"]
    assert (await client.get("/api/v1/legal/nonsense")).status_code == 404


async def test_new_terms_version_must_be_accepted(client):
    legal_admin = await make_staff(client, "admin")
    u = await make_user(client)
    assert (await client.get("/api/v1/auth/me", headers=u["headers"])).json()["pending_legal"] == []
    version = f"2.{uuid.uuid4().hex[:4]}"
    draft = await client.post("/api/v1/admin/legal", headers=legal_admin["headers"], json={
        "document_type": "terms", "version": version, "title": "Terms & Conditions",
        "content": "Updated terms content for testing purposes.", "summary_of_changes": "Clarified refunds.",
        "requires_acceptance": True})
    assert draft.status_code == 200 and draft.json()["status"] == "draft"
    doc_id = draft.json()["id"]
    # A teacher can't publish, and drafts aren't public.
    assert (await client.post(f"/api/v1/admin/legal/{doc_id}/publish", headers=u["headers"])).status_code == 403
    assert (await client.get("/api/v1/legal/terms")).json()["version"] != version
    assert (await client.post(f"/api/v1/admin/legal/{doc_id}/publish", headers=legal_admin["headers"])).json()[
        "status"] == "published"
    # Published versions are immutable.
    r = await client.put(f"/api/v1/admin/legal/{doc_id}", headers=legal_admin["headers"], json={
        "document_type": "terms", "version": version, "title": "x" * 5, "content": "changed after publishing!!"})
    assert r.status_code == 409
    pending = (await client.get("/api/v1/auth/me", headers=u["headers"])).json()["pending_legal"]
    assert [d["version"] for d in pending] == [version]
    r = await client.post("/api/v1/me/legal/accept", headers=u["headers"], json={"document_types": ["terms"]})
    assert r.json()["pending"] == [] and r.json()["accepted"][0]["version"] == version
    assert (await client.get("/api/v1/auth/me", headers=u["headers"])).json()["pending_legal"] == []
    history = (await client.get("/api/v1/legal/terms")).json()["versions"]
    assert len(history) >= 2 and history[0]["version"] == version  # older versions stay viewable


async def test_marketing_consent_is_separate_and_toggleable(client):
    u = await make_user(client)
    c = (await client.get("/api/v1/me/consents", headers=u["headers"])).json()
    assert c["marketing"] == {"marketing_email": False, "marketing_sms": False, "marketing_whatsapp": False}
    assert c["consents"]["terms"]["granted"] is True
    c = (await client.put("/api/v1/me/consents", headers=u["headers"], json={"marketing_email": True})).json()
    assert c["marketing"]["marketing_email"] is True
    c = (await client.put("/api/v1/me/consents", headers=u["headers"], json={"marketing_email": False})).json()
    assert c["marketing"]["marketing_email"] is False
    r = await client.post("/api/v1/me/cookie-consent", headers=u["headers"], json={"analytics": True})
    assert r.status_code == 200
    assert (await client.get("/api/v1/me/consents", headers=u["headers"])).json()["cookies"]["analytics"] is True


# --------------------------------------------------------------------------- notifications & usage warnings


async def test_usage_warnings_fire_once_per_threshold(client):
    from app.services import usage

    u = await make_user(client, plan="free")  # 60 credits a month
    uid = uuid.UUID(u["id"])
    async with get_sessionmaker()() as db:
        await usage.consume(db, uid, 31, "lesson_generation", "test")  # 51%
        await db.commit()
        await usage.consume(db, uid, 1, "lesson_generation", "test")  # still 50% band: no repeat
        await db.commit()
        await usage.consume(db, uid, 28, "lesson_generation", "test")  # 100%
        await db.commit()
        titles = [n.title for n in (await db.execute(select(Notification).where(
            Notification.user_id == uid, Notification.type == "usage"))).scalars().all()]
        mails = (await db.execute(select(EmailOutbox).where(EmailOutbox.user_id == uid,
                                                            EmailOutbox.template == "usage_warning"))).scalars().all()
        events = (await db.execute(select(AnalyticsEvent).where(AnalyticsEvent.user_id == uid,
                                                                AnalyticsEvent.name == "lesson_generated"))).scalars().all()
    assert titles.count("You've used 50% of this month's credits") == 1
    assert "You've used all your credits this month" in titles
    assert len(mails) == 1 and len(events) == 3
    listing = (await client.get("/api/v1/me/notifications", headers=u["headers"])).json()
    assert listing["unread"] >= 2


async def test_notifications_are_private(client):
    from app.services.notify import notify

    a = await make_user(client)
    b = await make_user(client)
    async with get_sessionmaker()() as db:
        await notify(db, uuid.UUID(a["id"]), "system", "For A only")
        await db.commit()
    mine = (await client.get("/api/v1/me/notifications", headers=a["headers"])).json()["items"]
    nid = next(n["id"] for n in mine if n["title"] == "For A only")
    assert all(n["title"] != "For A only" for n in
               (await client.get("/api/v1/me/notifications", headers=b["headers"])).json()["items"])
    # B can't mark A's notification read.
    assert (await client.post("/api/v1/me/notifications/read", headers=b["headers"], json={"ids": [nid]})).json()[
        "updated"] == 0
    assert (await client.post("/api/v1/me/notifications/read", headers=a["headers"], json={"ids": [nid]})).json()[
        "updated"] == 1


# --------------------------------------------------------------------------- support


async def test_support_ticket_flow_and_isolation(client):
    support = await make_staff(client, "support")
    a = await make_user(client)
    b = await make_user(client)
    t = (await client.post("/api/v1/support/tickets", headers=a["headers"], json={
        "kind": "bug", "subject": "Slides are blank", "body": "Lesson 3 downloads empty slides."})).json()
    assert t["number"] > 1000 and t["status"] == "open"
    assert (await client.get(f"/api/v1/support/tickets/{t['id']}", headers=b["headers"])).status_code == 404
    assert (await client.post(f"/api/v1/support/tickets/{t['id']}/messages", headers=b["headers"],
                              json={"body": "hi"})).status_code == 404
    await client.post(f"/api/v1/admin/support/tickets/{t['id']}/messages", headers=support["headers"],
                      json={"body": "Customer on old template, check renderer.", "internal": True})
    await client.post(f"/api/v1/admin/support/tickets/{t['id']}/messages", headers=support["headers"],
                      json={"body": "Thanks — we've fixed it, please try again."})
    mine = (await client.get(f"/api/v1/support/tickets/{t['id']}", headers=a["headers"])).json()
    bodies = [m["body"] for m in mine["messages"]]
    assert "Customer on old template, check renderer." not in bodies  # internal notes stay internal
    assert mine["status"] == "pending" and mine["messages"][-1]["author"] == "Clastio support"
    staff_view = (await client.get(f"/api/v1/admin/support/tickets/{t['id']}", headers=support["headers"])).json()
    assert len(staff_view["messages"]) == 3
    await client.post(f"/api/v1/support/tickets/{t['id']}/messages", headers=a["headers"], json={"body": "Works!"})
    assert (await client.get(f"/api/v1/support/tickets/{t['id']}", headers=a["headers"])).json()["status"] == "open"
    async with get_sessionmaker()() as db:
        mails = (await db.execute(select(EmailOutbox).where(EmailOutbox.user_id == uuid.UUID(a["id"]),
                                                            EmailOutbox.template == "ticket_reply"))).scalars().all()
    assert len(mails) == 1  # the internal note didn't email the teacher
    analyst = await make_staff(client, "analyst")
    assert (await client.get("/api/v1/admin/support/tickets", headers=analyst["headers"])).status_code == 403


async def test_feature_request_is_a_ticket_kind(client):
    u = await make_user(client)
    r = await client.post("/api/v1/support/tickets", headers=u["headers"], json={
        "kind": "feature_request", "subject": "Arabic voiceover", "body": "Would love narrated slides."})
    assert r.status_code == 200
    items = (await client.get("/api/v1/support/tickets?kind=feature_request", headers=u["headers"])).json()["items"]
    assert items and items[0]["kind"] == "feature_request"


# --------------------------------------------------------------------------- announcements


async def test_announcements_audience_and_schedule(client):
    admin = await make_staff(client, "admin")
    u = await make_user(client)
    title = f"Maintenance {uuid.uuid4().hex[:4]}"
    r = await client.post("/api/v1/admin/announcements", headers=admin["headers"],
                          json={"kind": "maintenance", "title": title, "body": "Sunday 2am", "audience": "teachers"})
    assert r.status_code == 200
    assert any(a["title"] == title for a in (await client.get("/api/v1/announcements", headers=u["headers"])).json()[
        "items"])
    await client.put(f"/api/v1/admin/announcements/{r.json()['id']}", headers=admin["headers"],
                     json={"kind": "maintenance", "title": title, "audience": "teachers", "active": False})
    assert all(a["title"] != title for a in (await client.get("/api/v1/announcements", headers=u["headers"])).json()[
        "items"])
    r = await client.post("/api/v1/admin/announcements", headers=admin["headers"],
                          json={"title": "Bad link", "link": "javascript:alert(1)"})
    assert r.status_code == 422


# --------------------------------------------------------------------------- webhooks


async def test_webhook_records_status_hash_and_blocks_tampered_replay(client):
    u = await make_user(client, plan="free")
    msg = f"msg_{uuid.uuid4().hex}"
    pay = {"payment_id": f"pay_{uuid.uuid4().hex[:8]}", "total_amount": 1900, "currency": "AED",
           "metadata": {"user_id": u["id"], "kind": "media_pack", "pack_code": "starter"}}
    r = await dodo_post(client, {"type": "payment.succeeded", "data": pay}, msg_id=msg)
    assert r.json()["result"] == "processed"
    tampered = {**pay, "total_amount": 1}
    r = await dodo_post(client, {"type": "payment.succeeded", "data": tampered}, msg_id=msg)
    assert r.json()["result"] == "rejected"
    async with get_sessionmaker()() as db:
        ev = (await db.execute(select(WebhookEvent).where(WebhookEvent.event_id == msg))).scalars().one()
        assert ev.status == "processed" and len(ev.payload_hash) == 64 and ev.processed_at
        sec = (await db.execute(select(SecurityEvent).where(SecurityEvent.type == "webhook_rejected")
                                .order_by(SecurityEvent.created_at.desc()))).scalars().first()
        assert sec.details["reason"] == "payload_changed" and sec.severity == "critical"
    media = (await client.get("/api/v1/media", headers=u["headers"])).json()
    assert media["balance"] == 50  # credited exactly once


async def test_failed_webhook_is_recorded_and_retried(client, monkeypatch):
    from app.services import billing

    calls = {"n": 0}
    real = billing.handle_dodo_event

    async def flaky(db, event, event_id=""):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("database hiccup")
        return await real(db, event, event_id)

    monkeypatch.setattr(billing, "handle_dodo_event", flaky)
    u = await make_user(client, plan="free")
    msg = f"msg_{uuid.uuid4().hex}"
    event = {"type": "payment.failed", "data": {"payment_id": f"pay_{uuid.uuid4().hex[:6]}", "total_amount": 9900,
                                                "currency": "AED", "error_message": "Card declined",
                                                "metadata": {"user_id": u["id"]}}}
    try:
        r = await dodo_post(client, event, msg_id=msg)
        assert r.status_code == 500
    except RuntimeError:
        pass  # the ASGI test transport re-raises server errors
    async with get_sessionmaker()() as db:
        ev = (await db.execute(select(WebhookEvent).where(WebhookEvent.event_id == msg))).scalars().one()
        assert ev.status == "failed" and "database hiccup" in ev.error_message
    r = await dodo_post(client, event, msg_id=msg)  # the gateway retries
    assert r.json()["result"] == "processed"
    async with get_sessionmaker()() as db:
        ev = (await db.execute(select(WebhookEvent).where(WebhookEvent.event_id == msg)
                               .execution_options(populate_existing=True))).scalars().one()
        assert ev.status == "processed" and ev.retry_count == 1 and ev.error_message is None
        p = (await db.execute(select(Payment).where(Payment.provider_ref == event["data"]["payment_id"]))).scalars().one()
        assert p.status == "failed" and p.failure_reason == "Card declined"


async def test_subscription_activation_notifies_and_tracks(client):
    u = await make_user(client, plan="free")
    sub_id = f"sub_{uuid.uuid4().hex[:10]}"
    data = {"subscription_id": sub_id, "status": "active", "metadata": {"user_id": u["id"], "plan_code": "pro",
                                                                          "interval": "month"},
            "customer": {"customer_id": "cus_x"}, "next_billing_date": "2026-11-01T00:00:00Z"}
    await dodo_post(client, {"type": "subscription.active", "data": data})
    await dodo_post(client, {"type": "subscription.cancelled", "data": {**data, "status": "cancelled"}})
    async with get_sessionmaker()() as db:
        names = [e.name for e in (await db.execute(select(AnalyticsEvent).where(
            AnalyticsEvent.user_id == uuid.UUID(u["id"])))).scalars().all()]
        templates = [e.template for e in (await db.execute(select(EmailOutbox).where(
            EmailOutbox.user_id == uuid.UUID(u["id"])))).scalars().all()]
    assert "subscription_activated" in names and "subscription_canceled" in names
    assert "subscription_confirmed" in templates and "subscription_cancelled" in templates


async def test_bad_webhook_signature_is_a_security_event(client):
    from tests.test_media_and_dodo import dodo_post as post

    await post(client, {"type": "payment.succeeded", "data": {}}, key="whsec_" + "d3Jvbmcta2V5LXdyb25nLWtleS0xMjM0NTY=")
    async with get_sessionmaker()() as db:
        ev = (await db.execute(select(SecurityEvent).where(SecurityEvent.type == "webhook_rejected",
                                                           SecurityEvent.details["reason"].astext == "invalid_signature")
                               )).scalars().first()
    assert ev is not None


# --------------------------------------------------------------------------- email outbox


async def test_email_worker_logs_without_smtp(client):
    from app.services.notify import send_pending_emails

    await make_user(client)
    await send_pending_emails(limit=200)
    async with get_sessionmaker()() as db:
        left = (await db.execute(select(EmailOutbox).where(EmailOutbox.status == "queued"))).scalars().all()
        logged = (await db.execute(select(EmailOutbox).where(EmailOutbox.status == "logged"))).scalars().first()
    assert logged is not None and len(left) < 5
