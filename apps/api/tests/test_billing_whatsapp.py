from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

from tests.conftest import make_user


def stripe_sig(payload: bytes, secret: str = "whsec_test_secret") -> str:
    ts = int(time.time())
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


async def post_stripe(client, event: dict):
    payload = json.dumps(event).encode()
    return await client.post("/api/v1/webhooks/stripe", content=payload,
                             headers={"stripe-signature": stripe_sig(payload), "content-type": "application/json"})


async def test_plans_are_configurable_data(client):
    plans = (await client.get("/api/v1/billing/plans")).json()
    codes = [p["code"] for p in plans["items"]]
    assert codes == ["free", "teacher", "pro", "assistant"]
    assert plans["vat_rate"] == 0.05


async def test_stripe_webhook_signature_required(client):
    payload = json.dumps({"id": "evt_bad", "type": "x", "data": {"object": {}}}).encode()
    r = await client.post("/api/v1/webhooks/stripe", content=payload, headers={"stripe-signature": "t=1,v1=nope"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_signature"


async def test_stripe_subscription_lifecycle(client):
    u = await make_user(client, plan="free")
    sub_id = f"sub_{uuid.uuid4().hex[:8]}"
    checkout = {"id": f"evt_{uuid.uuid4().hex[:8]}", "type": "checkout.session.completed", "data": {"object": {
        "mode": "subscription", "subscription": sub_id, "customer": "cus_123", "client_reference_id": u["id"],
        "metadata": {"user_id": u["id"], "plan_code": "pro", "interval": "month"}}}}
    r = await post_stripe(client, checkout)
    assert r.status_code == 200 and r.json()["result"] == "processed"
    assert (await post_stripe(client, checkout)).json()["result"] == "duplicate"  # idempotent
    usage = (await client.get("/api/v1/me/usage", headers=u["headers"])).json()
    assert usage["plan"]["code"] == "pro"
    period_end = int(time.time()) + 30 * 86400
    upd = {"id": f"evt_{uuid.uuid4().hex[:8]}", "type": "customer.subscription.updated", "data": {"object": {
        "id": sub_id, "status": "active", "customer": "cus_123", "cancel_at_period_end": True,
        "items": {"data": [{"current_period_start": int(time.time()), "current_period_end": period_end,
                            "price": {"recurring": {"interval": "month"}}}]}, "metadata": {"plan_code": "pro"}}}}
    await post_stripe(client, upd)
    sub = (await client.get("/api/v1/billing/subscription", headers=u["headers"])).json()
    assert sub["subscription"]["cancel_at_period_end"] is True
    paid = {"id": f"evt_{uuid.uuid4().hex[:8]}", "type": "invoice.paid", "data": {"object": {
        "id": f"in_{uuid.uuid4().hex[:8]}", "subscription": sub_id, "amount_paid": 15645, "currency": "aed",
        "total_taxes": [{"amount": 745}], "hosted_invoice_url": "https://invoice.example"}}}
    await post_stripe(client, paid)
    sub = (await client.get("/api/v1/billing/subscription", headers=u["headers"])).json()
    assert sub["payments"][0]["amount"] == 156.45 and sub["payments"][0]["tax"] == 7.45
    failed = {"id": f"evt_{uuid.uuid4().hex[:8]}", "type": "invoice.payment_failed",
              "data": {"object": {"id": "in_x", "subscription": sub_id}}}
    await post_stripe(client, failed)
    assert (await client.get("/api/v1/billing/subscription", headers=u["headers"])).json()["subscription"][
        "status"] == "past_due"
    deleted = {"id": f"evt_{uuid.uuid4().hex[:8]}", "type": "customer.subscription.deleted",
               "data": {"object": {"id": sub_id, "status": "canceled"}}}
    await post_stripe(client, deleted)
    assert (await client.get("/api/v1/me/usage", headers=u["headers"])).json()["plan"]["code"] == "free"


def wa_sig(body: bytes) -> str:
    return "sha256=" + hmac.new(b"wa_test_secret", body, hashlib.sha256).hexdigest()


async def test_whatsapp_verify_and_signature(client):
    r = await client.get("/api/v1/webhooks/whatsapp",
                         params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"})
    assert r.text == "42"
    bad = await client.get("/api/v1/webhooks/whatsapp",
                           params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "42"})
    assert bad.status_code == 403
    body = json.dumps({"entry": []}).encode()
    assert (await client.post("/api/v1/webhooks/whatsapp", content=body,
                              headers={"x-hub-signature-256": "sha256=deadbeef"})).status_code == 401


async def test_whatsapp_link_and_commands(client):
    u = await make_user(client, plan="assistant")
    h = u["headers"]
    free = await make_user(client, plan="free")
    assert (await client.post("/api/v1/whatsapp/link", headers=free["headers"], json={"phone": "+971501110000"})
            ).status_code == 402
    link = (await client.post("/api/v1/whatsapp/link", headers=h, json={"phone": "052 777 8888"})).json()
    assert link["phone"] == "+971527778888"

    async def inbound(text: str, payload: str | None = None):
        msg = {"from": "971527778888", "id": f"wamid.{uuid.uuid4().hex}"}
        msg.update({"type": "button", "button": {"text": text, "payload": payload}} if payload else
                   {"type": "text", "text": {"body": text}})
        body = json.dumps({"entry": [{"changes": [{"value": {"messages": [msg]}}]}]}).encode()
        r = await client.post("/api/v1/webhooks/whatsapp", content=body, headers={"x-hub-signature-256": wa_sig(body)})
        assert r.status_code == 200

    await inbound("LINK 000000")
    status = (await client.get("/api/v1/whatsapp", headers=h)).json()
    assert status["contact"]["verified"] is False
    await inbound(f"LINK {link['code']}")
    status = (await client.get("/api/v1/whatsapp", headers=h)).json()
    assert status["contact"]["verified"] and status["contact"]["opted_in"]
    await inbound("STOP")
    assert (await client.get("/api/v1/whatsapp", headers=h)).json()["contact"]["opted_in"] is False
    await inbound("START")
    await inbound("What did I teach last week?")
    msgs = (await client.get("/api/v1/whatsapp", headers=h)).json()["messages"]
    outs = [m for m in msgs if m["direction"] == "out"]
    assert any("connected" in m["body"] for m in outs)
    assert any("Paused" in m["body"] for m in outs)
    assert all(m["status"] in ("simulated", "sent") for m in outs)
    r = await client.post("/api/v1/whatsapp/send-today", headers=h)
    assert r.json()["sent"] is True
    usage = (await client.get("/api/v1/me/usage", headers=h)).json()
    assert usage["usage"]["whatsapp_messages"]["used"] == 1  # only the template message is metered


async def test_unknown_numbers_are_ignored(client):
    msg = {"from": "971500000001", "id": f"wamid.{uuid.uuid4().hex}", "type": "text", "text": {"body": "hello"}}
    body = json.dumps({"entry": [{"changes": [{"value": {"messages": [msg]}}]}]}).encode()
    r = await client.post("/api/v1/webhooks/whatsapp", content=body, headers={"x-hub-signature-256": wa_sig(body)})
    assert r.status_code == 200


async def test_admin_metrics_and_limits(client):
    from app.core.db import get_sessionmaker
    from app.models import User

    admin = await make_user(client, plan=None)
    async with get_sessionmaker()() as db:
        u = await db.get(User, uuid.UUID(admin["id"]))
        u.role = "admin"
        await db.commit()
    m = (await client.get("/api/v1/admin/metrics", headers=admin["headers"])).json()
    assert m["users"]["total"] >= 1 and "mrr_aed" in m["revenue"]
    costs = (await client.get("/api/v1/admin/ai-costs", headers=admin["headers"])).json()
    assert "by_model" in costs
    r = await client.put("/api/v1/admin/plans/free", headers=admin["headers"], json={"limits": {"max_lectures": 4}})
    assert r.status_code == 200 and r.json()["limits"]["max_lectures"] == 4
    await client.put("/api/v1/admin/plans/free", headers=admin["headers"], json={"limits": {"max_lectures": 3}})
    r = await client.put("/api/v1/admin/settings/credit_costs", headers=admin["headers"], json={"slide": 2})
    assert r.json()["slide"] == 2
    await client.put("/api/v1/admin/settings/credit_costs", headers=admin["headers"], json={"slide": 1})


async def test_scheduler_runs_once_across_workers(client):
    """Two workers ticking at the same moment must not both send the morning message."""
    from sqlalchemy import select, text

    from app.core.db import get_sessionmaker
    from app.models import User, WhatsAppContact
    from app.services import whatsapp as wa
    from app.services.planner import today_for, working_days

    u = await make_user(client, plan="assistant")
    uid = uuid.UUID(u["id"])
    async with get_sessionmaker()() as db:
        db.add(WhatsAppContact(user_id=uid, phone_e164="+971529990001", verified=True, opted_in=True,
                               daily_time="00:00", reflection_time="23:59", quiet_start="00:00", quiet_end="00:00"))
        await db.commit()

    async def last_sent():
        async with get_sessionmaker()() as db:
            c = (await db.execute(select(WhatsAppContact).where(WhatsAppContact.user_id == uid))).scalars().one()
            return c.last_daily_sent_on

    # Another worker is mid-tick (holds the lock): this tick must do nothing.
    async with get_sessionmaker()() as other:
        await other.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": wa.SCHEDULER_LOCK_KEY})
        assert await wa.scheduler_tick() == {"daily": 0, "reflection": 0}
        assert await last_sent() is None
        await other.rollback()

    # Once the lock is free the tick runs and records the send, so a second tick doesn't repeat it.
    await wa.scheduler_tick()
    async with get_sessionmaker()() as db:
        user = await db.get(User, uid)
        today = today_for(user)
        is_working_day = today.weekday() in await working_days(db, user)
    if is_working_day:
        assert await last_sent() == today
