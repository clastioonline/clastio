"""Media studio (teachers) and its admin controls."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.deps import DB, AdminUser, CurrentUser
from app.core.errors import AppError, NotFound
from app.core.ratelimit import rate_limit
from app.core.storage import get_storage
from app.models import AuditLog, CreditLedger, MediaItem, User
from app.services import billing
from app.services import media as media_svc

router = APIRouter(tags=["media"])


def _public_packs(cfg: dict) -> list[dict]:
    return [{"code": p["code"], "name": p["name"], "credits": p["credits"], "price_aed": p.get("price_aed")}
            for p in cfg.get("packs", []) if p.get("active", True)]


@router.get("/media")
async def list_media(user: CurrentUser, db: DB, limit: int = 60):
    cfg = await media_svc.media_config()
    items = (await db.execute(select(MediaItem).where(MediaItem.owner_id == user.id)
                              .order_by(MediaItem.created_at.desc()).limit(min(limit, 200)))).scalars().all()
    bal = await media_svc.balance(db, user)
    await db.commit()  # persists a monthly allowance grant, if one was due
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "balance": bal,
        "pricing": {"image": media_svc.cost_of(cfg, "image", None),
                    "video_per_second": int(cfg.get("video_credits_per_second", 3))},
        "video_seconds": cfg.get("video_seconds", [4, 8]),
        "styles": cfg.get("styles", []),
        "packs": _public_packs(cfg),
        "online_payments": await billing.active_provider_name() is not None,
        "items": [media_svc.item_out(m) for m in items],
    }


class MediaIn(BaseModel):
    kind: str = Field(pattern="^(image|video)$")
    prompt: str = Field(min_length=3, max_length=1000)
    style: str | None = None
    aspect: str = "16:9"
    seconds: int | None = None


@router.post("/media", dependencies=[Depends(rate_limit("media", 30, 3600))])
async def create_media(data: MediaIn, user: CurrentUser, db: DB):
    item = await media_svc.create(db, user, kind=data.kind, prompt=data.prompt, style=data.style,
                                  aspect=data.aspect, seconds=data.seconds)
    return media_svc.item_out(item)


@router.get("/media/{media_id}")
async def get_media(media_id: uuid.UUID, user: CurrentUser, db: DB):
    return media_svc.item_out(await media_svc.get_item(db, user, media_id))


@router.delete("/media/{media_id}")
async def delete_media(media_id: uuid.UUID, user: CurrentUser, db: DB):
    item = await media_svc.get_item(db, user, media_id)
    if item.status in ("queued", "running"):
        raise AppError("busy", "This item is still being generated.", 409)
    if item.storage_key:
        await get_storage().delete(item.storage_key)
    await db.delete(item)
    await db.commit()
    return {"ok": True}


@router.post("/media/packs/{code}/checkout")
async def buy_pack(code: str, user: CurrentUser, db: DB):
    cfg = await media_svc.media_config()
    pack = next((p for p in cfg.get("packs", []) if p["code"] == code and p.get("active", True)), None)
    if pack is None:
        raise NotFound("Pack")
    provider = await billing.get_provider()
    url = await provider.checkout_one_time(
        user, name=f"Media credits — {pack['name']} ({pack['credits']} credits)",
        amount_aed=float(pack.get("price_aed") or 0), product_id=pack.get("dodo_product_id") or None,
        metadata={"kind": "media_pack", "pack_code": pack["code"]})
    return {"url": url}


# --------------------------------------------------------------------------- admin


@router.get("/admin/media", tags=["admin"])
async def admin_media(_: AdminUser, db: DB, days: int = 30):
    from datetime import timedelta

    from app.core.db import utcnow

    since = utcnow() - timedelta(days=days)
    by_kind = (await db.execute(
        select(MediaItem.kind, MediaItem.status, func.count(), func.coalesce(func.sum(MediaItem.credits), 0))
        .where(MediaItem.created_at >= since).group_by(MediaItem.kind, MediaItem.status))).all()
    sold = (await db.execute(select(func.coalesce(func.sum(CreditLedger.amount), 0)).where(
        CreditLedger.resource == media_svc.RESOURCE, CreditLedger.reason.like("media_pack:%"),
        CreditLedger.created_at >= since))).scalar_one()
    recent = (await db.execute(select(MediaItem, User.email).join(User, User.id == MediaItem.owner_id)
                               .order_by(MediaItem.created_at.desc()).limit(20))).all()
    return {
        "config": await media_svc.media_config(),
        "billing": await billing_setting(),
        "usage": [{"kind": k, "status": s, "count": c, "credits": int(cr)} for k, s, c, cr in by_kind],
        "credits_sold": int(sold),
        "recent": [{**media_svc.item_out(m), "owner": email} for m, email in recent],
    }


async def billing_setting() -> dict:
    from app.core.config import get_settings
    from app.services.settings import get_setting

    s = get_settings()
    return {**(await get_setting("billing")), "active": await billing.active_provider_name(),
            "configured": {"dodo": bool(s.dodo_payments_api_key), "dodo_webhook": bool(s.dodo_payments_webhook_key),
                           "dodo_environment": s.dodo_payments_environment, "stripe": bool(s.stripe_secret_key),
                           "stripe_webhook": bool(s.stripe_webhook_secret)}}


class GrantIn(BaseModel):
    email: str
    amount: int = Field(ge=-100_000, le=100_000)
    note: str = ""


@router.post("/admin/media/grant", tags=["admin"])
async def admin_grant(data: GrantIn, admin: AdminUser, db: DB):
    user = (await db.execute(select(User).where(User.email == data.email.lower().strip()))).scalars().first()
    if user is None:
        raise NotFound("User")
    await media_svc.grant(db, user.id, data.amount, f"admin_grant:{data.note[:60]}" if data.note else "admin_grant")
    db.add(AuditLog(actor_id=admin.id, action="media_credits_grant", target=str(user.id),
                    details={"amount": data.amount, "note": data.note}))
    await db.commit()
    return {"email": user.email, "balance": await media_svc.balance(db, user)}
