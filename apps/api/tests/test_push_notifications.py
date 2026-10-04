"""Device opt-in, ownership, deduplication and logout protections on a real isolated database."""

import base64
import uuid
from unittest.mock import AsyncMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import func, select

from app.core.db import get_sessionmaker
from app.models.push import PushDelivery, PushSubscription
from app.services import push
from tests.conftest import make_user


@pytest.fixture(autouse=True)
def configured_push(monkeypatch):
    monkeypatch.setattr("app.api.routes.push.push_configured", lambda: True)
    monkeypatch.setattr(push, "push_configured", lambda: True)


def encode(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def subscription():
    key = ec.generate_private_key(ec.SECP256R1())
    return {"endpoint": f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4().hex}", "keys": {
        "p256dh": encode(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)),
        "auth": encode(b"test-auth-secret")}}


async def test_configuration_is_gracefully_unavailable(client, monkeypatch):
    user = await make_user(client, plan="free")
    monkeypatch.setattr(push, "push_configured", lambda: False)
    monkeypatch.setattr("app.api.routes.push.push_configured", lambda: False)
    response = await client.get("/api/v1/me/push", headers=user["headers"])
    assert response.status_code == 200 and not response.json()["configured"]
    assert response.json()["public_key"] is None
    response = await client.post("/api/v1/me/push/subscriptions", headers=user["headers"], json=subscription())
    assert response.status_code == 503


async def test_devices_are_private_and_subscription_secrets_not_returned(client, monkeypatch):
    monkeypatch.setattr(push, "push_configured", lambda: True)
    a, b = await make_user(client, plan="free"), await make_user(client, plan="free")
    device = subscription()
    enrolled = await client.post("/api/v1/me/push/subscriptions", headers=a["headers"], json=device)
    assert enrolled.status_code == 200, enrolled.text
    pid = enrolled.json()["id"]
    response = await client.get("/api/v1/me/push", headers=a["headers"])
    item = response.json()["items"][0]
    assert item["active"] and item["id"] == pid
    assert "endpoint" not in item and "auth" not in item and "p256dh" not in item
    assert device["endpoint"] not in response.text and device["keys"]["auth"] not in response.text
    assert (await client.get("/api/v1/me/push", headers=b["headers"])).json()["items"] == []
    forbidden = await client.patch(f"/api/v1/me/push/subscriptions/{pid}", headers=b["headers"], json={"marketing_enabled": True})
    assert forbidden.status_code == 404
    deleted = await client.delete(f"/api/v1/me/push/subscriptions/{pid}", headers=b["headers"])
    assert deleted.json() == {"removed": False}
    assert (await client.delete(f"/api/v1/me/push/subscriptions/{pid}", headers=a["headers"])).json() == {"removed": True}


async def test_shared_browser_reenrollment_discards_old_account_messages(client, monkeypatch):
    monkeypatch.setattr(push, "push_configured", lambda: True)
    a, b = await make_user(client, plan="free"), await make_user(client, plan="free")
    device = subscription()
    assert (await client.post("/api/v1/me/push/subscriptions", headers=a["headers"], json=device)).status_code == 200
    async with get_sessionmaker()() as db:
        assert await push.queue_push(db, uuid.UUID(a["id"]), "product", "A lesson", "Private", "/lessons", "once") == 1
        await db.commit()
    assert (await client.post("/api/v1/me/push/subscriptions", headers=b["headers"], json=device)).status_code == 200
    assert (await client.get("/api/v1/me/push", headers=a["headers"])).json()["items"] == []
    async with get_sessionmaker()() as db:
        assert (await db.execute(select(func.count()).select_from(PushDelivery).where(PushDelivery.user_id == uuid.UUID(a["id"])))) .scalar_one() == 0


async def test_duplicate_events_and_revoked_sessions_do_not_send(client, monkeypatch):
    from app.services.notify import notify

    monkeypatch.setattr(push, "push_configured", lambda: True)
    user = await make_user(client, plan="free")
    response = await client.post("/api/v1/me/push/subscriptions", headers=user["headers"], json=subscription())
    assert response.status_code == 200
    async with get_sessionmaker()() as db:
        for _ in range(2):
            await notify(db, uuid.UUID(user["id"]), "product", "Lesson ready", "Open your lesson", "/lessons", "job:one")
        await db.commit()
        rows = (await db.execute(select(PushDelivery).where(PushDelivery.user_id == uuid.UUID(user["id"])))) .scalars().all()
        assert len(rows) == 1
    assert (await client.post("/api/v1/auth/logout", headers=user["headers"])).status_code == 200
    provider = AsyncMock(return_value=201)
    monkeypatch.setattr(push, "deliver_push", provider)
    await push.send_pending_push()
    provider.assert_not_awaited()
    async with get_sessionmaker()() as db:
        row = (await db.execute(select(PushDelivery).where(PushDelivery.user_id == uuid.UUID(user["id"])))) .scalar_one()
        assert row.status == "suppressed"


async def test_announcement_requires_separate_push_consent_and_category(client, monkeypatch):
    from app.services.notifications import set_prefs

    monkeypatch.setattr(push, "push_configured", lambda: True)
    user = await make_user(client, plan="free")
    device = subscription()
    response = await client.post("/api/v1/me/push/subscriptions", headers=user["headers"], json=device)
    pid = response.json()["id"]
    async with get_sessionmaker()() as db:
        assert await push.queue_push(db, uuid.UUID(user["id"]), "announcement", "News", "Hello", "/notifications", "news:one") == 0
        await set_prefs(db, uuid.UUID(user["id"]), {"announcement": {"push": True}})
        assert await push.queue_push(db, uuid.UUID(user["id"]), "announcement", "News", "Hello", "/notifications", "news:two") == 0
        await db.commit()
    assert (await client.patch(f"/api/v1/me/push/subscriptions/{pid}", headers=user["headers"], json={"marketing_enabled": True})).status_code == 200
    async with get_sessionmaker()() as db:
        assert await push.queue_push(db, uuid.UUID(user["id"]), "announcement", "News", "Hello", "/notifications", "news:three") == 1
        assert await push.queue_push(db, uuid.UUID(user["id"]), "announcement", "News", "Hello", "/notifications", "news:three") == 0
        await db.commit()


async def test_subscription_registration_rejects_nonpush_endpoints(client, monkeypatch):
    monkeypatch.setattr(push, "push_configured", lambda: True)
    user = await make_user(client, plan="free")
    device = subscription()
    device["endpoint"] = "https://169.254.169.254/latest/meta-data"
    response = await client.post("/api/v1/me/push/subscriptions", headers=user["headers"], json=device)
    assert response.status_code == 422
    async with get_sessionmaker()() as db:
        assert not (await db.execute(select(PushSubscription).where(PushSubscription.user_id == uuid.UUID(user["id"])))) .scalars().all()
