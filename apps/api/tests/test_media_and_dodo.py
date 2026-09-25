from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from standardwebhooks import Webhook

from tests.conftest import make_user

DODO_KEY = "whsec_dGVzdC1kb2RvLXdlYmhvb2stc2VjcmV0LTEyMzQ="


async def dodo_post(client, event: dict, *, msg_id: str | None = None, key: str = DODO_KEY):
    payload = json.dumps(event)
    msg_id = msg_id or f"msg_{uuid.uuid4().hex}"
    now = datetime.now(UTC)
    headers = {"webhook-id": msg_id, "webhook-timestamp": str(int(now.timestamp())),
               "webhook-signature": Webhook(key).sign(msg_id, now, payload), "content-type": "application/json"}
    return await client.post("/api/v1/webhooks/dodo", content=payload.encode(), headers=headers)


async def make_admin(client) -> dict:
    from app.core.db import get_sessionmaker
    from app.models import User

    a = await make_user(client, plan=None, name="Admin")
    async with get_sessionmaker()() as db:
        (await db.get(User, uuid.UUID(a["id"]))).role = "admin"
        await db.commit()
    return a


async def plan_code(client, headers) -> str:
    return (await client.get("/api/v1/me/usage", headers=headers)).json()["plan"]["code"]


async def test_dodo_webhook_rejects_bad_signature(client):
    event = {"type": "payment.succeeded", "data": {"payment_id": "pay_x"}}
    r = await dodo_post(client, event, key="whsec_" + "d3Jvbmcta2V5LXdyb25nLWtleS0xMjM0NTY=")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_signature"


async def test_dodo_subscription_lifecycle(client):
    u = await make_user(client, plan="free")
    sub_id = f"sub_{uuid.uuid4().hex[:10]}"
    meta = {"user_id": u["id"], "plan_code": "pro", "interval": "month", "kind": "subscription"}
    sub = {"subscription_id": sub_id, "status": "active", "product_id": "pdt_pro_m", "metadata": meta,
           "customer": {"customer_id": "cus_1", "email": u["email"]}, "payment_frequency_interval": "Month",
           "previous_billing_date": "2026-09-01T00:00:00Z", "next_billing_date": "2026-10-01T00:00:00Z",
           "cancel_at_next_billing_date": False}
    r = await dodo_post(client, {"type": "subscription.active", "data": sub}, msg_id="msg_sub_active_1")
    assert r.json()["result"] == "processed"
    assert await plan_code(client, u["headers"]) == "pro"
    # Replayed delivery is ignored.
    r = await dodo_post(client, {"type": "subscription.active", "data": sub}, msg_id="msg_sub_active_1")
    assert r.json()["result"] == "duplicate"

    pay = {"payment_id": f"pay_{uuid.uuid4().hex[:8]}", "subscription_id": sub_id, "total_amount": 15645,
           "tax": 745, "currency": "AED", "metadata": meta, "customer": {"customer_id": "cus_1"}}
    await dodo_post(client, {"type": "payment.succeeded", "data": pay})
    billing = (await client.get("/api/v1/billing/subscription", headers=u["headers"])).json()
    assert billing["subscription"]["provider"] == "dodo"
    assert billing["payments"][0]["amount"] == 156.45 and billing["payments"][0]["tax"] == 7.45

    await dodo_post(client, {"type": "subscription.on_hold", "data": {**sub, "status": "on_hold"}})
    assert (await client.get("/api/v1/billing/subscription", headers=u["headers"])).json()[
        "subscription"]["status"] == "past_due"
    await dodo_post(client, {"type": "subscription.cancelled", "data": {**sub, "status": "cancelled"}})
    assert await plan_code(client, u["headers"]) == "free"


async def test_media_pack_bought_with_dodo_is_credited_once(client):
    u = await make_user(client, plan="free")
    pay_id = f"pay_{uuid.uuid4().hex[:8]}"
    data = {"payment_id": pay_id, "total_amount": 1900, "currency": "AED",
            "metadata": {"user_id": u["id"], "kind": "media_pack", "pack_code": "starter"}}
    await dodo_post(client, {"type": "payment.succeeded", "data": data})
    await dodo_post(client, {"type": "payment.succeeded", "data": data})  # new delivery id, same payment
    assert (await client.get("/api/v1/media", headers=u["headers"])).json()["balance"] == 50


async def test_media_pack_matched_by_product_when_metadata_missing(client):
    admin = await make_admin(client)
    media = (await client.get("/api/v1/admin/settings", headers=admin["headers"])).json()["media"]
    media["packs"][1]["dodo_product_id"] = "pdt_creator_pack"
    r = await client.put("/api/v1/admin/settings/media", headers=admin["headers"], json=media)
    assert r.status_code == 200
    u = await make_user(client, plan="free")
    sub_less = {"payment_id": f"pay_{uuid.uuid4().hex[:8]}", "total_amount": 5900, "currency": "AED",
                "metadata": {"user_id": u["id"]}, "product_cart": [{"product_id": "pdt_creator_pack", "quantity": 1}]}
    await dodo_post(client, {"type": "payment.succeeded", "data": sub_less})
    assert (await client.get("/api/v1/media", headers=u["headers"])).json()["balance"] == 200


class FakeCheckoutSessions:
    calls: list[dict] = []

    async def create(self, **kwargs):
        FakeCheckoutSessions.calls.append(kwargs)

        class R:
            checkout_url = "https://test.checkout.dodopayments.com/session/cks_123"
        return R()


class FakeDodo:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.checkout_sessions = FakeCheckoutSessions()


async def test_dodo_checkout_uses_admin_product_ids(client, monkeypatch):
    import dodopayments

    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "dodo_payments_api_key", "test_key")
    monkeypatch.setattr(dodopayments, "AsyncDodoPayments", FakeDodo)
    FakeCheckoutSessions.calls.clear()
    admin = await make_admin(client)
    r = await client.put("/api/v1/admin/settings/billing", headers=admin["headers"],
                         json={"provider": "dodo", "dodo_products": {"teacher_month": "pdt_teacher_m"}})
    assert r.status_code == 200
    u = await make_user(client, plan="free")
    plans = (await client.get("/api/v1/billing/plans")).json()
    assert plans["online_payments"] and plans["payment_provider"] == "dodo"

    r = await client.post("/api/v1/billing/checkout", headers=u["headers"], json={"plan": "teacher"})
    assert r.json()["url"].startswith("https://test.checkout.dodopayments.com/")
    call = FakeCheckoutSessions.calls[-1]
    assert call["product_cart"] == [{"product_id": "pdt_teacher_m", "quantity": 1}]
    assert call["metadata"]["user_id"] == u["id"] and call["metadata"]["plan_code"] == "teacher"
    assert call["customer"]["email"] == u["email"]
    # A plan without a Dodo product is refused clearly instead of charging the wrong amount.
    r = await client.post("/api/v1/billing/checkout", headers=u["headers"], json={"plan": "pro", "interval": "year"})
    assert r.status_code == 503

    # Media pack checkout needs its product id too.
    r = await client.post("/api/v1/media/packs/starter/checkout", headers=u["headers"])
    assert r.status_code == 503
    media = (await client.get("/api/v1/admin/settings", headers=admin["headers"])).json()["media"]
    media["packs"][0]["dodo_product_id"] = "pdt_starter"
    await client.put("/api/v1/admin/settings/media", headers=admin["headers"], json=media)
    r = await client.post("/api/v1/media/packs/starter/checkout", headers=u["headers"])
    assert r.status_code == 200
    assert FakeCheckoutSessions.calls[-1]["metadata"] == {"user_id": u["id"], "kind": "media_pack",
                                                          "pack_code": "starter"}
    await client.put("/api/v1/admin/settings/billing", headers=admin["headers"], json={"provider": "auto"})


async def test_admin_settings_are_validated(client):
    admin = await make_admin(client)
    h = admin["headers"]
    assert (await client.put("/api/v1/admin/settings/billing", headers=h, json={"provider": "paypal"})
            ).status_code == 422
    media = (await client.get("/api/v1/admin/settings", headers=h)).json()["media"]
    bad = {**media, "packs": [{"code": "x", "name": "X", "credits": -5, "price_aed": 10}]}
    assert (await client.put("/api/v1/admin/settings/media", headers=h, json=bad)).status_code == 422
    assert (await client.put("/api/v1/admin/settings/media", headers=h, json={**media, "video_model": "sora"})
            ).status_code == 422
    assert (await client.get("/api/v1/public/config")).json()["default_skin"] == "forest"
    assert (await client.put("/api/v1/admin/settings/ui", headers=h, json={"default_skin": "classic"})
            ).status_code == 200
    assert (await client.get("/api/v1/public/config")).json()["default_skin"] == "classic"
    await client.put("/api/v1/admin/settings/ui", headers=h, json={"default_skin": "forest"})


async def test_media_studio_charges_credits_and_labels_output(client):
    admin = await make_admin(client)
    u = await make_user(client, plan="free")
    h = u["headers"]
    r = await client.post("/api/v1/media", headers=h, json={"kind": "image", "prompt": "A plant cell"})
    assert r.status_code == 402 and r.json()["error"]["details"]["needed"] == 2

    r = await client.post("/api/v1/admin/media/grant", headers=admin["headers"],
                          json={"email": u["email"], "amount": 20, "note": "welcome"})
    assert r.json()["balance"] == 20

    r = await client.post("/api/v1/media", headers=h, json={
        "kind": "image", "prompt": "Children planting seeds in a school garden", "style": "photorealistic",
        "aspect": "16:9"})
    img = r.json()
    assert r.status_code == 200 and img["status"] == "ready", img
    assert img["ai_generated"] and img["demo"] and img["url"]
    assert "ai-generated-image" in img["url"]  # the download name says what it is
    assert (await client.get(img["url"])).status_code == 200

    r = await client.post("/api/v1/media", headers=h, json={"kind": "video", "prompt": "A seed sprouting",
                                                            "aspect": "16:9", "seconds": 4})
    vid = r.json()
    assert vid["status"] == "ready" and vid["credits"] == 12 and vid["mime_type"] == "image/gif"
    listing = (await client.get("/api/v1/media", headers=h)).json()
    assert listing["balance"] == 6 and len(listing["items"]) == 2
    assert listing["pricing"] == {"image": 2, "video_per_second": 3}

    # Durations and styles are admin-controlled.
    r = await client.post("/api/v1/media", headers=h, json={"kind": "video", "prompt": "x y z", "seconds": 30})
    assert r.status_code == 400
    r = await client.post("/api/v1/media", headers=h, json={"kind": "image", "prompt": "a cat", "style": "anime"})
    assert r.status_code == 400
    assert (await client.delete(f"/api/v1/media/{img['id']}", headers=h)).json()["ok"]


async def test_failed_generation_refunds_credits(client, monkeypatch):
    from app.ai.base import AIRefusal
    from app.ai.service import AIService
    from app.jobs.queue import REFUSAL_MESSAGE

    admin = await make_admin(client)
    u = await make_user(client, plan="free")
    await client.post("/api/v1/admin/media/grant", headers=admin["headers"], json={"email": u["email"], "amount": 5})

    async def refuse(self, *a, **k):
        raise AIRefusal("declined", provider="openai")

    monkeypatch.setattr(AIService, "image", refuse)
    item = (await client.post("/api/v1/media", headers=u["headers"],
                              json={"kind": "image", "prompt": "Something the model declines"})).json()
    assert item["status"] == "failed" and item["error"] == REFUSAL_MESSAGE
    assert (await client.get("/api/v1/media", headers=u["headers"])).json()["balance"] == 5


async def test_media_disabled_by_admin(client):
    admin = await make_admin(client)
    media = (await client.get("/api/v1/admin/settings", headers=admin["headers"])).json()["media"]
    await client.put("/api/v1/admin/settings/media", headers=admin["headers"], json={**media, "enabled": False})
    try:
        u = await make_user(client, plan="free")
        r = await client.post("/api/v1/media", headers=u["headers"], json={"kind": "image", "prompt": "a map"})
        assert r.status_code == 403
    finally:
        await client.put("/api/v1/admin/settings/media", headers=admin["headers"], json={**media, "enabled": True})


async def test_openai_video_adapter():
    from types import SimpleNamespace

    from app.ai.base import AIRefusal
    from app.ai.openai_provider import OpenAIProvider

    class Videos:
        status, error = "completed", None

        async def create_and_poll(self, **kw):
            self.kw = kw
            return SimpleNamespace(id="video_1", status=self.status, error=self.error)

        async def download_content(self, video_id, variant):
            assert (video_id, variant) == ("video_1", "video")
            return SimpleNamespace(content=b"MP4DATA")

    p = OpenAIProvider()
    p._client = SimpleNamespace(videos=Videos())
    res = await p.generate_video("sora-2", "a seed sprouting", 5, "9:16")
    assert res.data == b"MP4DATA" and res.media_type == "video/mp4" and res.usage.video_seconds == 4
    assert p._client.videos.kw == {"model": "sora-2", "prompt": "a seed sprouting", "seconds": "4",
                                   "size": "720x1280"}
    p._client.videos.status = "failed"
    p._client.videos.error = SimpleNamespace(code="moderation_blocked", message="blocked")
    with pytest.raises(AIRefusal):
        await p.generate_video("sora-2", "x", 8, "16:9")


async def test_gemini_video_adapter_polls_until_done(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from app.ai.gemini_provider import GeminiProvider

    async def no_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    video = SimpleNamespace(video_bytes=b"VEO", mime_type="video/mp4")
    done = SimpleNamespace(done=True, error=None, result=None,
                           response=SimpleNamespace(generated_videos=[SimpleNamespace(video=video)],
                                                    rai_media_filtered_reasons=None))
    polls = []

    class Models:
        async def generate_videos(self, **kw):
            self.kw = kw
            return SimpleNamespace(done=False)

    class Operations:
        async def get(self, op):
            polls.append(op)
            return done

    p = GeminiProvider()
    p._client = SimpleNamespace(aio=SimpleNamespace(models=Models(), operations=Operations()))
    res = await p.generate_video("veo-3.0-fast-generate-001", "a volcano", 12, "16:9")
    assert res.data == b"VEO" and res.usage.video_seconds == 8 and len(polls) == 1
    assert p._client.aio.models.kw["config"].duration_seconds == 8
