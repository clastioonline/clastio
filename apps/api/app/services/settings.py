"""Admin-editable runtime settings (stored in app_settings) with defaults."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.core.db import get_sessionmaker, utcnow
from app.models import AppSetting

DEFAULTS: dict[str, Any] = {
    # Credit cost per generated artefact (plan limits are expressed in credits).
    "credit_costs": {
        "slide": 1, "course_plan": 2, "worksheet": 4, "quiz": 3, "homework": 2, "assessment": 5,
        "lesson_plan_doc": 1, "ai_image": 3, "assistant_message": 0, "style_analysis": 2,
    },
    "model_routing": {},
    "ai_pricing": {},
    "feature_flags": {"whatsapp": True, "ai_images": True, "openverse": True, "vision_qc": False},
    "qc": {"min_body_pt": 16, "min_title_pt": 24, "max_repair_attempts": 2, "max_words_per_slide": 70},
    # Which payment gateway checkout uses: "auto" picks Dodo Payments when its key is set, else Stripe.
    # Product ids are created in the gateway dashboard; they are not secrets, so admins manage them here.
    "billing": {"provider": "auto", "dodo_products": {}},
    # Media studio: AI image and video generation, paid with media credits (separate from lesson credits).
    "media": {
        "enabled": True,
        "image_credits": 2,
        "video_credits_per_second": 3,
        "video_seconds": [4, 8],
        "image_model": "",  # "provider:model"; empty uses the image tier routing
        "video_model": "",  # empty uses the video tier routing
        "styles": ["photorealistic", "natural classroom photo", "illustration", "diagram", "3d render",
                   "watercolour", "cartoon"],
        "packs": [
            {"code": "starter", "name": "Starter", "credits": 50, "price_aed": 19, "dodo_product_id": "",
             "active": True},
            {"code": "creator", "name": "Creator", "credits": 200, "price_aed": 59, "dodo_product_id": "",
             "active": True},
            {"code": "studio", "name": "Studio", "credits": 600, "price_aed": 149, "dodo_product_id": "",
             "active": True},
        ],
    },
    # Look of the web app. Teachers can still pick their own in Settings.
    "ui": {"default_skin": "forest"},
}


async def get_app_settings(keys: list[str] | None = None) -> dict[str, Any]:
    async with get_sessionmaker()() as s:
        q = select(AppSetting)
        if keys:
            q = q.where(AppSetting.key.in_(keys))
        rows = (await s.execute(q)).scalars().all()
    stored = {r.key: r.value for r in rows}
    out = {}
    for k in keys or list(DEFAULTS.keys() | stored.keys()):
        default = DEFAULTS.get(k)
        val = stored.get(k, default)
        if isinstance(default, dict) and isinstance(val, dict):
            val = {**default, **val}
        out[k] = val
    return out


async def get_setting(key: str) -> Any:
    return (await get_app_settings([key]))[key]


async def set_setting(key: str, value: Any) -> None:
    async with get_sessionmaker()() as s:
        row = await s.get(AppSetting, key)
        if row is None:
            s.add(AppSetting(key=key, value=value, updated_at=utcnow()))
        else:
            row.value = value
            row.updated_at = utcnow()
        await s.commit()
