"""Push privacy, SSRF boundaries, encryption, consent and retries without remote delivery."""

import base64
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.config import Settings
from app.core.db import utcnow
from app.services import notifications, push


def encode(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def keys():
    key = ec.generate_private_key(ec.SECP256R1())
    return key, encode(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))


@pytest.fixture
def settings(monkeypatch):
    private, public = keys()
    settings = Settings(_env_file=None, environment="test", web_push_public_key=public,
                        web_push_private_key=encode(private.private_numbers().private_value.to_bytes(32, "big")),
                        web_push_subject="mailto:notifications@example.com")
    monkeypatch.setattr(push, "get_settings", lambda: settings)
    return settings


def device():
    _, public = keys()
    return SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), session_id=uuid.uuid4(),
                           endpoint="https://fcm.googleapis.com/fcm/send/test-secret-endpoint", p256dh=public,
                           auth=encode(b"test-auth-secret"), marketing_enabled=False)


@pytest.mark.parametrize("endpoint", [
    "http://fcm.googleapis.com/fcm/send/id", "https://127.0.0.1/path", "https://169.254.169.254/latest/meta-data",
    "https://fcm.googleapis.com.attacker.example/fcm/send/id", "https://attacker.push.apple.com.evil/path",
    "https://fcm.googleapis.com:8080/fcm/send/id", "https://user:pass@fcm.googleapis.com/fcm/send/id",
    "https://fcm.googleapis.com/unknown", "https://fcm.googleapis.com/fcm/send/id#fragment",
    "https://fcm.googleapis.com.:443/fcm/send/id", "https://push.apple.com.evil.example/id",
])
def test_endpoint_rejects_non_browser_services(endpoint):
    with pytest.raises(ValueError):
        push.validate_endpoint(endpoint)


@pytest.mark.parametrize("endpoint", [
    "https://fcm.googleapis.com/fcm/send/browser-token", "https://fcm.googleapis.com/wp/token",
    "https://updates.push.services.mozilla.com/wpush/v2/browser-token",
    "https://web.push.apple.com/browser-token", "https://wns2-bl2p.notify.windows.com/w/?token=browser-token",
])
def test_known_browser_push_services(endpoint):
    push.validate_endpoint(endpoint)


def test_vapid_requires_matching_pair_and_contact(settings):
    assert push.push_configured()
    settings.web_push_public_key = keys()[1]
    assert not push.push_configured()
    settings.web_push_private_key = None
    assert not push.push_configured()


@pytest.mark.parametrize("link", ["//evil.example", "https://evil.example", "/\\evil.example", None])
def test_external_notification_links_fall_back(link):
    assert push.safe_link(link) == "/notifications"


async def test_encryption_and_public_ip_are_pinned_no_redirects(monkeypatch, settings):
    target = device()
    resolver = AsyncMock(return_value="142.250.1.1")
    monkeypatch.setattr(push, "validate_public_image_url", resolver)
    seen = []

    def handle(request):
        seen.append(request)
        assert request.url.host == "142.250.1.1"
        assert request.headers["host"] == "fcm.googleapis.com"
        assert request.extensions["sni_hostname"] == "fcm.googleapis.com"
        assert request.headers["authorization"].startswith("vapid t=")
        assert request.headers["content-encoding"] == "aes128gcm"
        assert request.headers["ttl"] == "86400"
        assert b"Sensitive teacher material" not in request.content
        assert len(request.content) > 86
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})

    assert await push.deliver_push(target, {"title": "Sensitive teacher material", "tag": "one"},
                                   transport=httpx.MockTransport(handle)) == 302
    assert len(seen) == 1
    resolver.assert_awaited_once_with(target.endpoint)


async def test_private_dns_records_never_send(monkeypatch, settings):
    monkeypatch.setattr(push, "validate_public_image_url", AsyncMock(side_effect=ValueError("private DNS")))
    with pytest.raises(ValueError):
        await push.deliver_push(device(), {"title": "Test", "tag": "one"},
                                transport=httpx.MockTransport(lambda _: pytest.fail("Private IP request sent")))


def outbox(target):
    return SimpleNamespace(id=uuid.uuid4(), subscription_id=target.id, user_id=target.user_id, category="product",
                           title="Lesson ready", body="Open Clastio", link="/lessons", created_at=utcnow(),
                           attempts=0, status="queued", last_error=None, sent_at=None, send_after=utcnow())


def delivery_fixture(monkeypatch, rows, target, *, status="active", revoked=False, prefs=None, expired=False, role="teacher", admin_role=None):
    from app.models import User, UserSession
    from app.models.push import PushSubscription

    user = SimpleNamespace(id=target.user_id, status=status, role=role, admin_role=admin_role)
    session = SimpleNamespace(revoked_at=utcnow() if revoked else None, expires_at=utcnow() + timedelta(days=-1 if expired else 1))
    db = AsyncMock()
    db.__aenter__.return_value = db
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: rows))
    db.get.side_effect = lambda model, _: {User: user, UserSession: session, PushSubscription: target}[model]
    monkeypatch.setattr(push, "get_sessionmaker", lambda: lambda: db)
    monkeypatch.setattr(notifications, "get_prefs", AsyncMock(return_value=prefs or notifications.default_prefs()))
    provider = AsyncMock(return_value=201)
    monkeypatch.setattr(push, "deliver_push", provider)
    return db, provider


@pytest.mark.parametrize("restriction", ["inactive", "revoked_session", "category_disabled", "old_message", "marketing_no_consent"])
async def test_delivery_rechecks_current_choices(monkeypatch, settings, restriction):
    target = device()
    row = outbox(target)
    prefs = notifications.default_prefs()
    if restriction == "old_message":
        row.created_at -= timedelta(days=2)
    if restriction == "category_disabled":
        prefs["product"]["push"] = False
    if restriction == "marketing_no_consent":
        row.category = "announcement"
        prefs["announcement"]["push"] = True
    _, provider = delivery_fixture(monkeypatch, [row], target, status="deleted" if restriction == "inactive" else "active",
                                   revoked=restriction == "revoked_session", prefs=prefs)
    assert await push.send_pending_push() == 0
    assert row.status == "suppressed"
    provider.assert_not_awaited()


async def test_missing_keys_wait_without_consuming_attempts(monkeypatch, settings):
    settings.web_push_private_key = None
    target = device()
    row = outbox(target)
    _, provider = delivery_fixture(monkeypatch, [row], target)
    assert await push.send_pending_push() == 0
    assert row.status == "queued" and row.attempts == 0 and row.send_after > utcnow()
    provider.assert_not_awaited()


@pytest.mark.parametrize("status", [404, 410])
async def test_expired_browser_endpoints_are_removed(monkeypatch, settings, status):
    target = device()
    rows = [outbox(target), outbox(target)]
    db, provider = delivery_fixture(monkeypatch, rows, target)
    provider.return_value = status
    assert await push.send_pending_push() == 0
    db.delete.assert_awaited_once_with(target)
    assert provider.await_count == 1


async def test_transient_failure_retries_then_stops_without_secrets(monkeypatch, settings):
    target = device()
    row = outbox(target)
    _, provider = delivery_fixture(monkeypatch, [row], target)
    provider.side_effect = RuntimeError("private_endpoint_and_auth_key_must_not_be_logged")
    assert await push.send_pending_push() == 0
    assert row.status == "queued" and row.attempts == 1
    assert row.last_error == "Push delivery failed (RuntimeError)"
    row.attempts = 4
    assert await push.send_pending_push() == 0
    assert row.status == "failed" and row.attempts == 5


async def test_success_has_stable_duplicate_tag(monkeypatch, settings):
    target = device()
    row = outbox(target)
    _, provider = delivery_fixture(monkeypatch, [row], target)
    assert await push.send_pending_push() == 1
    assert row.status == "sent" and row.sent_at and row.attempts == 1
    assert provider.call_args.args[1]["tag"] == f"clastio:{row.id}"


async def test_normal_signin_expiry_does_not_withdraw_device_consent(monkeypatch, settings):
    target = device()
    row = outbox(target)
    _, provider = delivery_fixture(monkeypatch, [row], target, expired=True)
    assert await push.send_pending_push() == 1
    provider.assert_awaited_once()


@pytest.mark.parametrize("category", ["product", "usage", "feedback"])
async def test_promoted_admins_do_not_receive_old_teacher_pushes(monkeypatch, settings, category):
    target = device()
    row = outbox(target)
    row.category = category
    prefs = notifications.default_prefs()
    prefs[category]["push"] = True
    _, provider = delivery_fixture(monkeypatch, [row], target, role="admin", admin_role="super_admin", prefs=prefs)
    assert await push.send_pending_push() == 0
    assert row.status == "suppressed"
    provider.assert_not_awaited()


async def test_staff_permissions_are_rechecked_before_delivery(monkeypatch, settings):
    target = device()
    row = outbox(target)
    row.category, row.link = "staff", "/admin/system"
    _, provider = delivery_fixture(monkeypatch, [row], target, role="admin", admin_role="finance")
    assert await push.send_pending_push() == 0
    assert row.status == "suppressed"
    provider.assert_not_awaited()
