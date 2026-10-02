"""Visual assets for slides.

Order (cheapest and most reliable first):
  1. reuse an existing asset for the same query (owner's or shared)
  2. Openverse (openly licensed images, licence + attribution recorded)
  3. AI image generation (if a provider is configured and the plan allows)
  4. a clean, branded placeholder illustration (clearly replaceable; the notes say what to insert)
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import re
import uuid
from functools import lru_cache
from typing import Any

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import AIError
from app.ai.service import get_ai
from app.core.config import get_settings
from app.core.logging import log
from app.core.storage import get_storage
from app.engine.style.common import hex_to_rgb, mix
from app.generation.specs import SlideSpec
from app.models import Asset

logger = logging.getLogger("assets")
OPENVERSE_URL = "https://api.openverse.org/v1/images/"
MAX_IMAGE_BYTES = 6 * 1024 * 1024

EMOJI = [
    (r"plant|leaf|photosynth|tree|flower|seed|garden|palm", "🌱"), (r"water|rain|ocean|sea|river|cloud", "💧"),
    (r"sun|light|energy|solar", "☀️"), (r"cell|microb|bacteria|virus", "🦠"), (r"atom|molecule|chemi|element", "⚛️"),
    (r"earth|planet|world|geograph|map|country", "🌍"), (r"space|star|moon|rocket|astronom", "🚀"),
    (r"animal|habitat|camel|bird|fish|mammal", "🐪"), (r"body|heart|blood|organ|health", "🫀"),
    (r"math|fraction|number|algebra|equation|geometr", "➗"), (r"money|economy|trade|business", "💰"),
    (r"history|ancient|timeline|war|empire", "🏛️"), (r"computer|code|ai|robot|algorithm|data", "🤖"),
    (r"book|read|story|poem|english|language|write", "📚"), (r"music|sound|wave", "🎵"),
    (r"electric|circuit|magnet", "⚡"), (r"weather|climate|temperature", "🌦️"), (r"food|nutrition|diet", "🍎"),
]


def normalize_query(q: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (q or "").lower())).strip()[:120]


@lru_cache(maxsize=4)
def _emoji_font():
    for path in ("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",):
        try:
            return ImageFont.truetype(path, 109)
        except OSError:
            continue
    return None


def placeholder_illustration(description: str, primary: str, secondary: str, size=(1200, 900)) -> bytes:
    w, h = size
    top, bottom = hex_to_rgb(mix(primary, "#FFFFFF", 0.78)), hex_to_rgb(mix(secondary, "#FFFFFF", 0.82))
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))
    blobs = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blobs)
    p, s = hex_to_rgb(primary), hex_to_rgb(secondary)
    bd.ellipse((int(w * 0.62), int(-h * 0.18), int(w * 1.15), int(h * 0.45)), fill=p + (60,))
    bd.ellipse((int(-w * 0.15), int(h * 0.62), int(w * 0.35), int(h * 1.2)), fill=s + (70,))
    img = Image.alpha_composite(img.convert("RGBA"), blobs.filter(ImageFilter.GaussianBlur(30)))
    d = ImageDraw.Draw(img)
    r = int(min(w, h) * 0.22)
    cx, cy = w // 2, h // 2
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, 235))
    emoji = next((e for pat, e in EMOJI if re.search(pat, description.lower())), "🔎")
    font = _emoji_font()
    if font is not None:
        glyph = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        ImageDraw.Draw(glyph).text((80, 80), emoji, font=font, embedded_color=True, anchor="mm")
        glyph = glyph.resize((int(r * 1.15), int(r * 1.15)), Image.LANCZOS)
        img.alpha_composite(glyph, (cx - glyph.width // 2, cy - glyph.height // 2))
    d = ImageDraw.Draw(img)
    d.text((w // 2, int(h * .85)), "Image placeholder - replace in editor",
           fill=(45, 45, 45), font=ImageFont.load_default(size=28), anchor="mm")
    out = io.BytesIO()
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()


def _normalise_image(data: bytes, max_side: int = 1600) -> tuple[bytes, int, int]:
    with Image.open(io.BytesIO(data)) as im:
        im.load()
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        im.thumbnail((max_side, max_side))
        out = io.BytesIO()
        if im.mode == "RGBA":
            im.save(out, "PNG", optimize=True)
        else:
            im.save(out, "JPEG", quality=85, optimize=True)
        return out.getvalue(), im.width, im.height


async def search_openverse(query: str, client: httpx.AsyncClient) -> dict[str, Any] | None:
    params = {"q": query, "page_size": 8, "license_type": "commercial,modification", "mature": "false",
              "aspect_ratio": "wide", "size": "large"}
    try:
        r = await client.get(OPENVERSE_URL, params=params, timeout=8)
        r.raise_for_status()
        results = r.json().get("results", [])
    except (httpx.HTTPError, ValueError):
        return None
    for item in results:
        if (item.get("width") or 0) < 640 or not item.get("url"):
            continue
        try:
            img = await client.get(item["url"], timeout=12, follow_redirects=True)
            if img.status_code != 200 or len(img.content) > MAX_IMAGE_BYTES:
                continue
            Image.open(io.BytesIO(img.content)).verify()
        except (httpx.HTTPError, OSError, ValueError):
            continue
        lic = f"CC {item.get('license', '').upper()} {item.get('license_version', '')}".strip()
        attribution = item.get("attribution") or (
            f"\"{item.get('title') or 'Image'}\" by {item.get('creator') or 'unknown'} ({lic})")
        return {"data": img.content, "license": lic, "attribution": attribution, "source_url":
                item.get("foreign_landing_url")}
    return None


async def resolve_images(db: AsyncSession, *, owner_id: uuid.UUID, slides: list[SlideSpec], colors: dict[str, str],
                         job_id: uuid.UUID | None = None, allow_ai_images: int = 0,
                         openverse: bool = True, source_images: dict | None = None,
                         image_mode: str = "auto", teaching_context: str = "") -> tuple[dict[str, bytes], dict[str, int]]:
    """Attach an asset to every slide that wants a picture. Returns (asset_id -> bytes, counters)."""
    storage = get_storage()
    ai = get_ai()
    settings = get_settings()
    from app.services.settings import get_setting
    flags = await get_setting("feature_flags")
    allow_ai_images = allow_ai_images if flags.get("ai_images", True) and image_mode != "reuse" else 0
    openverse = openverse and flags.get("openverse", True) and image_mode != "ai"
    images: dict[str, bytes] = {}
    counters = {"reused": 0, "openverse": 0, "ai": 0, "placeholder": 0}
    ai_attempts = 0
    wanted = [s for s in slides if s.visual.kind in ("image", "diagram") and s.layout in ("image_text", "concept")
              and not s.asset_id and not s.visual.counting_groups]
    async with httpx.AsyncClient(headers={"User-Agent": "AI-Teacher-Assistant/1.0"}) as client:
        for s in wanted:
            source_image = (source_images or {}).get(s.visual.source_image_key)
            if source_image:
                try:
                    asset = await db.get(Asset, uuid.UUID(source_image["asset_id"]))
                except (ValueError, KeyError):
                    asset = None
                if asset and asset.owner_id in (owner_id, None) and asset.source == "upload":
                    s.asset_id = str(asset.id)
                    images[s.asset_id] = await storage.get(asset.storage_key)
                    counters["reused"] += 1
                    if asset.attribution:
                        s.sources.append({"type": "image", "attribution": asset.attribution})
                    continue
            s.visual.source_image_key = None
            query = normalize_query(s.visual.image_query or s.visual.description or s.title)
            existing = (await db.execute(select(Asset).where(
                or_(Asset.owner_id == owner_id, Asset.owner_id.is_(None)), Asset.tags.any(query),
                Asset.source != "placeholder",
                Asset.source.in_(["ai", "upload"]) if image_mode == "ai" or s.visual.kind == "diagram" else True).limit(1))).scalars().first()
            if existing:
                s.asset_id = str(existing.id)
                images[s.asset_id] = await storage.get(existing.storage_key)
                counters["reused"] += 1
                if existing.attribution:
                    s.sources.append({"type": "image", "attribution": existing.attribution})
                continue
            found = await search_openverse(query, client) if (openverse and settings.openverse_enabled and query and s.visual.kind != "diagram") \
                else None
            source, lic, attribution, data = None, None, None, None
            if found:
                source, lic, attribution, data = "openverse", found["license"], found["attribution"], found["data"]
            elif allow_ai_images > ai_attempts:
                ai_attempts += 1
                prompt = (f"Educational illustration for {teaching_context or 'a school lesson'}. Slide: {s.title}. "
                          f"Show exactly: {s.visual.description or s.title}. "
                          "Show only the requested subject with scientifically accurate parts and proportions. "
                          "Clear composition, distinct objects, plain light background, no decorative unrelated objects. "
                          "No text, no labels, "
                          "no watermarks.")
                try:
                    res = await ai.image(prompt, "1536x1024", owner_id=owner_id, job_id=job_id)
                except AIError:  # a missing picture must not fail the lesson; a placeholder is used instead
                    res = None
                if res:
                    source, lic, data = "ai", "AI-generated (owned by the teacher)", res.data
                    counters["ai"] += 1
            if data is None:
                data = await asyncio.to_thread(placeholder_illustration, s.visual.description or s.title,
                                               colors.get("primary", "#2563EB"), colors.get("secondary", "#F59E0B"))
                source, lic = "placeholder", "Generated placeholder"
                counters["placeholder"] += 1
            else:
                counters[source] += 1 if source == "openverse" else 0
            try:
                data, w, h = await asyncio.to_thread(_normalise_image, data)
            except (OSError, ValueError):
                data = await asyncio.to_thread(placeholder_illustration, s.title,
                    colors.get("primary", "#2563EB"), colors.get("secondary", "#F59E0B"))
                data, w, h = await asyncio.to_thread(_normalise_image, data)
                if source == "ai":
                    counters["ai"] -= 1
                elif source == "openverse":
                    counters["openverse"] -= 1
                source, lic = "placeholder", "Generated placeholder"
                counters["placeholder"] += 1
            if source == "placeholder":
                s.speaker_notes += "\nImage placeholder: upload a suitable image in the manual editor. A real illustration was unavailable."
            s.sources.append({"type": "image", "source": source, "description": s.visual.alt_text or s.visual.description})
            sha = hashlib.sha256(data).hexdigest()
            ext = "png" if data[:4] == b"\x89PNG" else "jpg"
            key = f"assets/{owner_id}/{sha}.{ext}"
            await storage.put(key, data)
            asset = Asset(owner_id=owner_id, kind="image", prompt=s.visual.description, source=source, license=lic,
                          attribution=attribution, width=w, height=h, storage_key=key, sha256=sha, tags=[query])
            db.add(asset)
            await db.flush()
            s.asset_id = str(asset.id)
            images[s.asset_id] = data
            if attribution:
                s.sources.append({"type": "image", "attribution": attribution})
    if counters["ai"]:
        log(logger, logging.INFO, "ai_images_generated", count=counters["ai"])
    return images, counters


async def load_images(db: AsyncSession, slides: list[SlideSpec]) -> dict[str, bytes]:
    storage = get_storage()
    out: dict[str, bytes] = {}
    ids = {s.asset_id for s in slides if s.asset_id}
    for aid in ids:
        try:
            asset = await db.get(Asset, uuid.UUID(aid))
        except ValueError:
            continue
        if asset:
            out[aid] = await storage.get(asset.storage_key)
    return out
