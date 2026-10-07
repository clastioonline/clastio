"""Encrypted Web Push, opt-in devices, and retryable delivery with no user-supplied HTTP targets."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import time
import uuid
from datetime import timedelta
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_sessionmaker, utcnow
from app.core.remote_images import validate_public_image_url
from app.models.push import PushDelivery, PushSubscription

MAX_ATTEMPTS = 5
# These services terminate standards-based browser subscriptions. Restrict paths as well as hostnames.
PUSH_HOSTS = {
    "fcm.googleapis.com": ("/fcm/send/", "/wp/"),
    "updates.push.services.mozilla.com": ("/wpush/v2/",),
    "updates.push.services.mozilla.com.cn": ("/wpush/v2/",),
    "web.push.apple.com": ("/",),
    "wns2-bl2p.notify.windows.com": ("/w/",),
}


def decode_key(value: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", value):
        raise ValueError("Invalid push key")
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def push_configured() -> bool:
    settings = get_settings()
    try:
        public, private = decode_key(settings.web_push_public_key or ""), decode_key(settings.web_push_private_key or "")
        key = ec.derive_private_key(int.from_bytes(private, "big"), ec.SECP256R1())
        expected = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        subject = urlsplit(settings.web_push_subject or "")
        valid_subject = subject.scheme == "mailto" and "@" in subject.path or subject.scheme == "https" and bool(subject.hostname)
        return len(private) == 32 and len(public) == 65 and public == expected and bool(valid_subject)
    except (ValueError, TypeError):
        return False


def validate_endpoint(endpoint: str) -> None:
    target = urlsplit(endpoint)
    try:
        port = target.port
    except ValueError:
        raise ValueError("Invalid push endpoint") from None
    if (target.scheme != "https" or not target.hostname or target.username or target.password
            or port not in (None, 443) or target.fragment or len(endpoint) > 2000):
        raise ValueError("Invalid push endpoint")
    host = target.hostname.lower()
    paths = PUSH_HOSTS.get(host)
    # Apple shards and Windows WNS are browser-owned push origins, not arbitrary subdomains.
    if not paths and re.fullmatch(r"[a-z0-9-]+\.push\.apple\.com", host):
        paths = ("/",)
    if not paths and re.fullmatch(r"[a-z0-9-]+\.notify\.windows\.com", host):
        paths = ("/w/",)
    if not paths or not any(target.path.startswith(path) and (len(target.path) > len(path) or bool(target.query)) for path in paths):
        raise ValueError("Unsupported browser push service")


def validate_subscription(endpoint: str, p256dh: str, auth: str) -> None:
    validate_endpoint(endpoint)
    key, secret = decode_key(p256dh), decode_key(auth)
    if len(key) != 65 or key[0] != 4 or len(secret) != 16:
        raise ValueError("Invalid push subscription keys")
    ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), key)


def endpoint_hash(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode()).hexdigest()


def safe_link(link: str | None) -> str:
    return link if link and link.startswith("/") and not link.startswith("//") and "\\" not in link and len(link) <= 500 else "/notifications"


def staff_target_allowed(user, link: str | None) -> bool:
    """Staff permission changes between queue and delivery must not leak a privileged alert."""
    from app.core.permissions import permissions_for

    if getattr(user, "role", "teacher") != "admin":
        return False
    permission = next((permission for prefix, permission in {
        "/admin/support": "support.manage", "/admin/billing": "billing.view",
        "/admin/security": "security.view", "/admin/system": "system.logs.view",
    }.items() if (link or "").startswith(prefix)), None)
    return permission is None or permission in permissions_for(user.role, getattr(user, "admin_role", None))


async def queue_push(db: AsyncSession, user_id: uuid.UUID, category: str, title: str, body: str,
                     link: str | None, dedupe_key: str) -> int:
    """Queue in the triggering transaction. A repeated event cannot queue the same device twice."""
    from app.models import User
    from app.services.notifications import get_prefs

    user = await db.get(User, user_id)
    if (not user or user.status != "active"
            or getattr(user, "role", "teacher") == "admin" and category in {"product", "usage", "feedback"}
            or category == "staff" and not staff_target_allowed(user, link)):
        return 0
    prefs = await get_prefs(db, user_id)
    if not prefs.get(category, {"push": category == "staff"}).get("push", False):
        return 0
    devices = (await db.execute(select(PushSubscription).where(PushSubscription.user_id == user_id))).scalars().all()
    queued = 0
    for device in devices:
        if category == "announcement" and not device.marketing_enabled:
            continue
        result = await db.execute(insert(PushDelivery).values(
            id=uuid.uuid4(), subscription_id=device.id, user_id=user_id, category=category, title=title[:200],
            body=body[:500], link=safe_link(link), dedupe_key=dedupe_key[:300], status="queued", attempts=0,
            send_after=utcnow(), created_at=utcnow()).on_conflict_do_nothing(index_elements=["subscription_id", "dedupe_key"]))
        queued += result.rowcount or 0
    return queued


async def deliver_push(device: PushSubscription, payload: dict, *, transport: httpx.AsyncBaseTransport | None = None) -> int:
    """Encrypt locally, then pin the validated public IP with Host/SNI. Never follow redirects or use proxies."""
    from py_vapid import Vapid
    from pywebpush import WebPusher

    validate_subscription(device.endpoint, device.p256dh, device.auth)
    address = await validate_public_image_url(device.endpoint)
    original = httpx.URL(device.endpoint)
    settings = get_settings()
    vapid = Vapid.from_string(settings.web_push_private_key)
    headers = vapid.sign({"aud": f"https://{original.host}", "sub": settings.web_push_subject,
                          "exp": int(time.time()) + 12 * 3600})
    data = WebPusher({"endpoint": device.endpoint, "keys": {"p256dh": device.p256dh, "auth": device.auth}}).encode(
        json.dumps(payload, ensure_ascii=False).encode(), content_encoding="aes128gcm")["body"]
    headers.update({"Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream",
                    "TTL": "86400", "Urgency": "normal", "Topic": hashlib.sha256(payload["tag"].encode()).hexdigest()[:32],
                    "Host": original.netloc.decode("ascii")})
    async with httpx.AsyncClient(transport=transport, trust_env=False, limits=httpx.Limits(max_keepalive_connections=0)) as client:
        async with client.stream("POST", original.copy_with(host=address), content=data, headers=headers,
                                 extensions={"sni_hostname": original.host}, timeout=12, follow_redirects=False) as response:
            # No need to read the service body; it can include endpoint secrets or enormous content.
            return response.status_code


async def send_pending_push(limit: int = 30) -> int:
    """At-least-once outbox. Provider Topic and browser tag replace duplicate retries after a process crash."""
    from app.models import User, UserSession
    from app.services.notifications import get_prefs

    sent = 0
    removed = set()
    async with get_sessionmaker()() as db:
        rows = (await db.execute(select(PushDelivery).where(PushDelivery.status == "queued", PushDelivery.send_after <= utcnow())
                                .order_by(PushDelivery.created_at).limit(limit).with_for_update(skip_locked=True))).scalars().all()
        for row in rows:
            if row.subscription_id in removed:
                continue
            device = await db.get(PushSubscription, row.subscription_id)
            user = await db.get(User, row.user_id)
            session = await db.get(UserSession, device.session_id) if device else None
            prefs = await get_prefs(db, row.user_id)
            if (not device or device.user_id != row.user_id or not user or user.status != "active"
                    or not session or session.revoked_at or session.expires_at <= utcnow()
                    or getattr(user, "role", "teacher") == "admin" and row.category in {"product", "usage", "feedback"}
                    or row.category == "staff" and not staff_target_allowed(user, row.link)
                    or not prefs.get(row.category, {"push": row.category == "staff"}).get("push", False)
                    or row.category == "announcement" and not device.marketing_enabled
                    or row.created_at < utcnow() - timedelta(days=1)):
                row.status, row.last_error = "suppressed", "Device consent, category, session, or account no longer active"
                continue
            if not push_configured():
                row.send_after, row.last_error = utcnow() + timedelta(minutes=5), "Web Push provider not configured"
                continue
            row.attempts += 1
            try:
                status = await deliver_push(device, {"title": row.title, "body": row.body, "url": row.link,
                                                    "tag": f"clastio:{row.id}"})
                if status in (404, 410):
                    # Removing a browser subscription cascades its queued messages and prevents repeat failures.
                    await db.delete(device)
                    removed.add(device.id)
                    await db.flush()
                    continue
                if 200 <= status < 300:
                    row.status, row.sent_at, row.last_error = "sent", utcnow(), None
                    sent += 1
                    continue
                row.last_error = f"Push service HTTP {status}"
                if status not in (408, 425, 429) and status < 500:
                    row.status = "failed"
                    continue
            except Exception as exc:  # noqa: BLE001 - never retain endpoint/key-bearing exception messages
                row.last_error = f"Push delivery failed ({type(exc).__name__})"
            if row.attempts >= MAX_ATTEMPTS:
                row.status = "failed"
            else:
                row.send_after = utcnow() + timedelta(minutes=2 ** row.attempts)
        await db.execute(delete(PushDelivery).where(PushDelivery.status != "queued",
                                                    PushDelivery.created_at < utcnow() - timedelta(days=30)))
        await db.commit()
    return sent
