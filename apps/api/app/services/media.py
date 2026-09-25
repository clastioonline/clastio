"""Media studio: AI image and video generation for teaching material, paid with media credits.

Media credits are a separate wallet from lesson credits, so admins can price this feature on its own:
- teachers buy credit packs (Dodo Payments or Stripe checkout), admins can grant credits, and a plan can include a
  monthly allowance (`limits.media_credits_monthly`);
- the cost per image, per video second, the allowed durations, styles, models and packs are all in the `media`
  app setting (Admin -> Media studio).

Every item is labelled as AI-generated in the app and in its download name, and the provider's file is stored
unchanged, so provenance data the provider embeds (such as C2PA content credentials) is kept.
"""

from __future__ import annotations

import asyncio
import io
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import get_ai
from app.core.db import get_sessionmaker, utcnow
from app.core.deps import can_access
from app.core.errors import AppError, LimitExceeded, NotFound
from app.core.storage import get_storage
from app.jobs.queue import JobContext, enqueue, run_inline_if_configured
from app.models import CreditLedger, MediaItem, User
from app.services import usage
from app.services.settings import get_setting

RESOURCE = "media_credits"
ASPECTS = {"16:9": "1536x1024", "9:16": "1024x1536", "1:1": "1024x1024"}
STYLE_HINTS = {
    "photorealistic": "photorealistic, natural lighting, realistic textures and proportions",
    "natural classroom photo": "a natural, candid photo of a real school classroom setting, soft daylight",
    "illustration": "clean modern illustration, friendly flat colours",
    "diagram": "clear educational diagram without text labels, simple shapes, high contrast, white background",
    "3d render": "soft 3D render, studio lighting",
    "watercolour": "watercolour painting, gentle textures",
    "cartoon": "friendly cartoon style suitable for young learners",
}
SAFETY = ("Appropriate for a school classroom. No text, logos or watermarks. Do not depict real, identifiable "
          "people.")


async def media_config() -> dict[str, Any]:
    return await get_setting("media")


def cost_of(cfg: dict[str, Any], kind: str, seconds: int | None) -> int:
    if kind == "image":
        return int(cfg.get("image_credits", 2))
    return int(cfg.get("video_credits_per_second", 3)) * int(seconds or 0)


async def _grant_monthly_allowance(db: AsyncSession, user: User) -> None:
    """Credit a plan's monthly media allowance once per billing period."""
    plan, sub = await usage.get_plan(db, user)
    monthly = int(plan.limits.get("media_credits_monthly") or 0)
    if monthly <= 0:
        return
    ref = f"monthly:{user.id}:{usage.period_start(sub).date().isoformat()}"
    if (await db.execute(select(CreditLedger.id).where(CreditLedger.ref == ref))).first() is None:
        db.add(usage.ledger_entry(user.id, monthly, "monthly_allowance", ref=ref, resource=RESOURCE))
        await db.flush()


async def balance(db: AsyncSession, user: User) -> int:
    await _grant_monthly_allowance(db, user)
    total = (await db.execute(select(func.coalesce(func.sum(CreditLedger.amount), 0)).where(
        CreditLedger.owner_id == user.id, CreditLedger.resource == RESOURCE))).scalar_one()
    return int(total)


async def grant(db: AsyncSession, user_id: uuid.UUID, amount: int, reason: str, ref: str | None = None) -> None:
    """Admin adjustment (positive or negative)."""
    if amount:
        db.add(usage.ledger_entry(user_id, amount, reason, ref=ref, resource=RESOURCE))


def item_out(m: MediaItem) -> dict[str, Any]:
    url = None
    if m.status == "ready" and m.storage_key:
        ext = m.storage_key.rsplit(".", 1)[-1]
        url = get_storage().signed_url(m.storage_key, f"ai-generated-{m.kind}-{str(m.id)[:8]}.{ext}")
    return {"id": str(m.id), "kind": m.kind, "prompt": m.prompt, "style": m.style, "aspect": m.aspect,
            "seconds": m.seconds, "status": m.status, "credits": m.credits, "provider": m.provider, "model": m.model,
            "mime_type": m.mime_type, "error": m.error, "url": url, "job_id": str(m.job_id) if m.job_id else None,
            "ai_generated": True, "demo": m.provider == "offline", "created_at": m.created_at.isoformat()}


async def create(db: AsyncSession, user: User, *, kind: str, prompt: str, style: str | None, aspect: str,
                 seconds: int | None) -> MediaItem:
    cfg = await media_config()
    if not cfg.get("enabled", True):
        raise AppError("feature_disabled", "The media studio is switched off right now.", 403)
    if kind not in ("image", "video"):
        raise AppError("bad_request", "Choose an image or a video.", 400)
    prompt = prompt.strip()
    if not 3 <= len(prompt) <= 1000:
        raise AppError("bad_request", "Describe what you want in 3 to 1000 characters.", 400)
    if style and style not in cfg.get("styles", []):
        raise AppError("bad_request", "Unknown style.", 400)
    if aspect not in ASPECTS or (kind == "video" and aspect == "1:1"):
        raise AppError("bad_request", "Unsupported aspect ratio.", 400)
    if kind == "video":
        allowed = [int(s) for s in cfg.get("video_seconds", [4, 8])]
        if seconds not in allowed:
            raise AppError("bad_request", f"Video length must be one of {allowed} seconds.", 400)
    else:
        seconds = None
    cost = cost_of(cfg, kind, seconds)
    await usage.check_generation_allowed(db, user, jobs=1)
    await usage.lock_user(db, user.id)  # balance check and charge happen atomically for this user
    available = await balance(db, user)
    if user.role != "admin" and available < cost:
        raise LimitExceeded(f"This {kind} needs {cost} media credits and you have {available}. Buy a pack to "
                            "continue.", {"resource": RESOURCE, "needed": cost, "balance": available})
    item = MediaItem(owner_id=user.id, kind=kind, prompt=prompt, style=style, aspect=aspect, seconds=seconds,
                     credits=cost, status="queued")
    db.add(item)
    await db.flush()
    # Charged up front and refunded automatically if generation fails.
    await usage.consume(db, user.id, cost, f"media_{kind}", str(item.id), resource=RESOURCE)
    job = await enqueue(db, "media_generation", {"media_id": str(item.id)}, owner_id=user.id, max_attempts=2)
    item.job_id = job.id
    left = available - cost
    if user.role != "admin" and left < cost_of(cfg, "image", None) * 3:
        from app.services.notifications import send

        await send(db, user, "media_credits_low", dedupe_key=f"media_low:{user.id}:{utcnow():%Y-%m}", balance=left)
    await db.commit()
    await run_inline_if_configured([job.id])
    await db.refresh(item)
    return item


async def get_item(db: AsyncSession, user: User, media_id: uuid.UUID) -> MediaItem:
    item = await db.get(MediaItem, media_id)
    if item is None or not can_access(user, item.owner_id):
        raise NotFound("Media")
    return item


def build_prompt(item: MediaItem) -> str:
    hint = STYLE_HINTS.get(item.style or "", item.style or "")
    motion = " Smooth, steady camera; a single continuous shot." if item.kind == "video" else ""
    return f"{item.prompt.strip()}. Style: {hint}.{motion} {SAFETY}".replace("..", ".")


def _demo_image(prompt: str, size: tuple[int, int]) -> bytes:
    from app.services.assets import placeholder_illustration

    return placeholder_illustration(prompt, "#4F46E5", "#F59E0B", size=size)


def _demo_video(prompt: str, aspect: str, seconds: int) -> bytes:
    """Offline demo: an animated GIF standing in for a video clip."""
    from PIL import Image

    size = (480, 270) if aspect == "16:9" else (270, 480)
    base = Image.open(io.BytesIO(_demo_image(prompt, (size[0] * 2, size[1] * 2)))).convert("RGB")
    frames = []
    count = max(8, seconds * 4)
    for i in range(count):
        zoom = 1 + 0.25 * i / count
        w, h = int(base.width / zoom), int(base.height / zoom)
        x, y = (base.width - w) // 2, (base.height - h) // 2
        frames.append(base.crop((x, y, x + w, y + h)).resize(size))
    out = io.BytesIO()
    frames[0].save(out, "GIF", save_all=True, append_images=frames[1:], duration=250, loop=0)
    return out.getvalue()


async def handle_media_generation(ctx: JobContext) -> dict[str, Any]:
    media_id = uuid.UUID(ctx.payload["media_id"])
    async with get_sessionmaker()() as db:
        item = await db.get(MediaItem, media_id)
        if item is None:
            return {"skipped": True}
        item.status = "running"
        await db.commit()
        kind, aspect, seconds, owner_id = item.kind, item.aspect, item.seconds, item.owner_id
        prompt = build_prompt(item)
    cfg = await media_config()
    ai = get_ai()
    await ctx.progress(20, "Generating your video" if kind == "video" else "Generating your image")
    if kind == "image":
        res = await ai.image(prompt, ASPECTS[aspect], owner_id=owner_id, job_id=ctx.job_id,
                             model=cfg.get("image_model") or None, task="media_image")
    else:
        res = await ai.video(prompt, int(seconds or 4), aspect, owner_id=owner_id, job_id=ctx.job_id,
                             model=cfg.get("video_model") or None)
    if res is not None:
        data, mime, provider, model = res.data, res.media_type, res.provider, res.model
    elif kind == "image":
        w, h = (int(v) for v in ASPECTS[aspect].split("x"))
        data = await asyncio.to_thread(_demo_image, prompt, (w // 2, h // 2))
        mime, provider, model = "image/png", "offline", "demo"
    else:
        data = await asyncio.to_thread(_demo_video, prompt, aspect, int(seconds or 4))
        mime, provider, model = "image/gif", "offline", "demo"
    await ctx.progress(85, "Saving")
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "video/mp4": "mp4",
           "image/gif": "gif"}.get(mime, "bin")
    key = f"media/{owner_id}/{media_id}.{ext}"
    await get_storage().put(key, data, mime)  # stored exactly as the provider returned it
    async with get_sessionmaker()() as db:
        item = await db.get(MediaItem, media_id)
        item.status, item.storage_key, item.mime_type = "ready", key, mime
        item.provider, item.model, item.size_bytes, item.error = provider, model, len(data), None
        await db.commit()
    return {"media_id": str(media_id), "provider": provider}


async def handle_media_failed(ctx: JobContext, error: str) -> None:
    async with get_sessionmaker()() as db:
        item = await db.get(MediaItem, uuid.UUID(ctx.payload["media_id"]))
        if item is None or item.status == "failed":
            return
        item.status, item.error = "failed", error[:1000]
        await usage.refund(db, item.owner_id, item.credits, f"media_{item.kind}_refund", str(item.id),
                           resource=RESOURCE)
        await db.commit()
