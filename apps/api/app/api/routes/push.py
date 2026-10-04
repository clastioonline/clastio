"""Authenticated, user-gesture device enrollment. Never returns endpoint URLs or encryption secrets."""

import uuid

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, text

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.deps import DB, CurrentUser
from app.core.errors import AppError
from app.models import User, UserSession
from app.models.push import PushDelivery, PushSubscription
from app.services.push import endpoint_hash, push_configured, validate_subscription

router = APIRouter(tags=["push notifications"])


class KeysIn(BaseModel):
    p256dh: str = Field(min_length=80, max_length=100)
    auth: str = Field(min_length=20, max_length=30)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=20, max_length=2000)
    keys: KeysIn
    device_name: str = Field(default="This browser", min_length=1, max_length=80)
    marketing_enabled: bool = False


class ConsentIn(BaseModel):
    marketing_enabled: bool


@router.get("/me/push")
async def push_devices(user: CurrentUser, db: DB):
    devices = (await db.execute(select(PushSubscription, UserSession).join(UserSession, PushSubscription.session_id == UserSession.id)
                               .where(PushSubscription.user_id == user.id).order_by(PushSubscription.created_at.desc()))).all()
    configured = push_configured()
    return {"configured": configured, "public_key": get_settings().web_push_public_key if configured else None,
            "items": [{"id": str(row.id), "endpoint_hash": row.endpoint_hash, "device_name": row.device_name,
                       "marketing_enabled": row.marketing_enabled, "consent_at": row.consent_at.isoformat(),
                       "active": not session.revoked_at}
                      for row, session in devices]}


@router.post("/me/push/subscriptions")
async def subscribe(data: SubscriptionIn, request: Request, user: CurrentUser, db: DB):
    if not push_configured():
        raise AppError("push_unavailable", "Device notifications are not configured yet.", 503)
    try:
        validate_subscription(data.endpoint, data.keys.p256dh, data.keys.auth)
    except ValueError:
        raise AppError("invalid_push_subscription", "This browser provided an invalid or unsupported push subscription.", 422) from None
    # Lock the account so parallel enrollment cannot bypass its device limit.
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    hashed = endpoint_hash(data.endpoint)
    endpoint_lock = int.from_bytes(bytes.fromhex(hashed)[:8], "big", signed=True)
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": endpoint_lock})
    existing = (await db.execute(select(PushSubscription).where(PushSubscription.endpoint_hash == hashed)
                                .with_for_update())).scalar_one_or_none()
    if existing and (existing.p256dh != data.keys.p256dh or existing.auth != data.keys.auth):
        raise AppError("push_subscription_changed", "Turn off browser notifications and enable them again.", 409)
    count = (await db.execute(select(func.count()).select_from(PushSubscription).where(PushSubscription.user_id == user.id))).scalar_one()
    if count >= 10 and (not existing or existing.user_id != user.id):
        raise AppError("push_device_limit", "Remove an old notification device before adding another.", 409)
    if existing:
        # A shared browser can switch accounts only by explicit opt-in. Discard the previous account's queued payloads.
        if existing.user_id != user.id:
            await db.execute(delete(PushDelivery).where(PushDelivery.subscription_id == existing.id))
        elif existing.session_id != request.state.session_id:
            await db.execute(delete(PushDelivery).where(PushDelivery.subscription_id == existing.id,
                                                        PushDelivery.status == "queued"))
        existing.user_id, existing.session_id = user.id, request.state.session_id
        existing.device_name, existing.marketing_enabled, existing.consent_at = data.device_name.strip(), data.marketing_enabled, utcnow()
        row = existing
    else:
        row = PushSubscription(user_id=user.id, session_id=request.state.session_id, endpoint_hash=hashed,
                               endpoint=data.endpoint, p256dh=data.keys.p256dh, auth=data.keys.auth,
                               device_name=data.device_name.strip(), marketing_enabled=data.marketing_enabled)
        db.add(row)
    await db.commit()
    return {"id": str(row.id), "enabled": True}


@router.patch("/me/push/subscriptions/{subscription_id}")
async def update_push_consent(subscription_id: uuid.UUID, data: ConsentIn, user: CurrentUser, db: DB):
    row = (await db.execute(select(PushSubscription).where(PushSubscription.id == subscription_id,
                                                         PushSubscription.user_id == user.id))).scalar_one_or_none()
    if not row:
        raise AppError("not_found", "Notification device not found.", 404)
    row.marketing_enabled = data.marketing_enabled
    row.consent_at = utcnow()
    await db.commit()
    return {"updated": True}


@router.delete("/me/push/subscriptions/{subscription_id}")
async def unsubscribe(subscription_id: uuid.UUID, user: CurrentUser, db: DB):
    result = await db.execute(delete(PushSubscription).where(PushSubscription.id == subscription_id,
                                                            PushSubscription.user_id == user.id))
    await db.commit()
    return {"removed": bool(result.rowcount)}
