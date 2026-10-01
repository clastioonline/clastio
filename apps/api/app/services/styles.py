"""Turn an uploaded deck into a TeacherStyleProfile + reusable Template (runs as a background job)."""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ChatMessage
from app.ai.service import get_ai
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.logging import log
from app.core.storage import get_storage
from app.engine.qc.visual import RenderError, inspect
from app.engine.render.renderer import DeckRenderer
from app.engine.style.pdf_analyzer import PdfAnalyzer
from app.engine.style.pptx_analyzer import analyze_pptx
from app.engine.template.builder import BUILTIN_STYLES, build_builtin, build_native, build_reconstructed
from app.engine.template.preview import PREVIEW_SLIDES
from app.models import StyleProfile, TeacherPreference, TeacherProfile, Template, UploadedFile

logger = logging.getLogger("styles")


def convert_ppt_to_pptx(data: bytes) -> bytes:
    soffice = shutil.which(get_settings().soffice_path) or "soffice"
    with tempfile.TemporaryDirectory(prefix="ata-ppt-") as tmp:
        src = Path(tmp) / "deck.ppt"
        src.write_bytes(data)
        subprocess.run([soffice, f"-env:UserInstallation=file://{tmp}/profile", "--headless", "--convert-to",
                        "pptx", "--outdir", tmp, str(src)], capture_output=True, timeout=180, check=False)
        out = Path(tmp) / "deck.pptx"
        if not out.exists():
            raise RenderError("Could not convert the .ppt file")
        return out.read_bytes()


async def _set_stage(file_id: uuid.UUID, stage: str, status: str = "processing", error: str | None = None,
                     **extra: Any) -> None:
    async with get_sessionmaker()() as s:
        f = await s.get(UploadedFile, file_id)
        if f:
            f.stage, f.status = stage, status
            if error is not None:
                f.error = error
            for k, v in extra.items():
                setattr(f, k, v)
            await s.commit()


def analyze_file(path: Path, ext: str) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    """Blocking: analyse and build the template. Returns (analysis, base_pptx, template_spec)."""
    if ext == "pptx":
        analysis = analyze_pptx(path)
        base, spec = build_native(path, analysis)
        return analysis, base, spec
    pa = PdfAnalyzer(path)
    analysis = pa.analyze()
    images = pa.decoration_images(analysis)
    base, spec = build_reconstructed(analysis, images=images)
    return analysis, base, spec


async def render_previews(template_id: uuid.UUID, base: bytes, spec: dict[str, Any]) -> list[str]:
    def _render() -> list[bytes]:
        pptx = DeckRenderer(base, spec).render(PREVIEW_SLIDES, {}, core_props={"title": "Preview"})
        return inspect(pptx, preview_dpi=48).thumbnails

    try:
        thumbs = await asyncio.to_thread(_render)
    except RenderError as e:
        log(logger, logging.WARNING, "template_preview_failed", error=str(e))
        return []
    keys = []
    revision = uuid.uuid4().hex
    for i, t in enumerate(thumbs, start=1):
        key = f"templates/{template_id}/previews/{revision}/{i}.webp"
        await get_storage().put(key, t, "image/webp")
        keys.append(key)
    return keys


async def describe_tone(analysis: dict[str, Any], owner_id: uuid.UUID) -> str | None:
    """Optional: a one-line description of the teacher's writing tone (live AI only)."""
    ai = get_ai()
    if ai.mode != "live":
        return None
    style = analysis.get("content_style", {})
    sample = "\n".join(style.get("sample_titles", [])[:8])
    try:
        return (await ai.text(task="tone_summary", tier="fast", system="Describe teaching tone in <= 12 words.",
                              messages=[ChatMessage("user", f"Slide titles from a teacher's deck:\n{sample}\n"
                                                            f"Stats: {style}")],
                              effort="low", max_tokens=200, owner_id=owner_id)).strip()[:200]
    except Exception:
        return None


async def process_style_upload(file_id: uuid.UUID, *, name: str | None = None) -> dict[str, Any]:
    storage = get_storage()
    async with get_sessionmaker()() as s:
        f = await s.get(UploadedFile, file_id)
        if f is None:
            raise ValueError("upload not found")
        owner_id, key, filename = f.owner_id, f.storage_key, f.filename
        ext = f.storage_key.rsplit(".", 1)[-1]
        # Never re-analyse identical content: reuse an existing profile built from the same file hash.
        existing = (await s.execute(select(Template).join(StyleProfile, Template.style_profile_id == StyleProfile.id)
                                    .where(StyleProfile.source_file_id == file_id))).scalars().first()
        if existing:
            await _set_stage(file_id, "Ready", "ready")
            return {"template_id": str(existing.id), "style_profile_id": str(existing.style_profile_id),
                    "reused": True}

    await _set_stage(file_id, "Analysing")
    data = await storage.get(key)
    with tempfile.TemporaryDirectory(prefix="ata-style-") as tmp:
        if ext == "ppt":
            await _set_stage(file_id, "Converting legacy PowerPoint")
            data = await asyncio.to_thread(convert_ppt_to_pptx, data)
            ext = "pptx"
        path = Path(tmp) / f"source.{ext}"
        path.write_bytes(data)
        await _set_stage(file_id, "Extracting design")
        analysis, base, spec = await asyncio.to_thread(analyze_file, path, ext)

    await _set_stage(file_id, "Understanding content", page_count=analysis.get("stats", {}).get("slides"))
    tone = await describe_tone(analysis, owner_id)
    if tone:
        analysis.setdefault("content_style", {})["tone"] = tone

    await _set_stage(file_id, "Creating template")
    template_id = uuid.uuid4()
    base_key = f"templates/{template_id}/base.pptx"
    await storage.put(base_key, base)
    previews = await render_previews(template_id, base, spec)
    title = name or Path(filename).stem.replace("_", " ").strip() or "My style"
    async with get_sessionmaker()() as s:
        profile = StyleProfile(owner_id=owner_id, source_file_id=file_id, name=title, profile=analysis)
        s.add(profile)
        await s.flush()
        tpl = Template(id=template_id, owner_id=owner_id, style_profile_id=profile.id, name=title,
                       mode=spec["mode"], base_storage_key=base_key, spec=spec, preview_keys=previews)
        s.add(tpl)
        tp = (await s.execute(select(TeacherProfile).where(TeacherProfile.user_id == owner_id))).scalars().first()
        if tp and not tp.default_template_id:
            tp.default_template_id = template_id
        await _store_style_preferences(s, owner_id, analysis)
        await s.commit()
    await _set_stage(file_id, "Ready", "ready")
    return {"template_id": str(template_id), "style_profile_id": str(profile.id), "mode": spec["mode"],
            "previews": len(previews)}


async def _store_style_preferences(db: AsyncSession, owner_id: uuid.UUID, analysis: dict[str, Any]) -> None:
    """Inferred (unconfirmed) preferences from the teacher's own slides."""
    cs = analysis.get("content_style", {})
    inferred = {
        "bullets_per_slide": cs.get("bullets_per_slide"),
        "words_per_bullet": cs.get("avg_words_per_bullet"),
        "uses_question_titles": (cs.get("question_titles_ratio") or 0) > 0.3,
        "uses_images": analysis.get("visual_rules", {}).get("uses_images"),
    }
    if cs.get("tone"):
        inferred["tone"] = cs["tone"]
    for key, value in inferred.items():
        if value is None:
            continue
        row = (await db.execute(select(TeacherPreference).where(TeacherPreference.user_id == owner_id,
                                                                  TeacherPreference.key == key))).scalars().first()
        if row is None:
            db.add(TeacherPreference(user_id=owner_id, key=key, value=value, source="inferred", confidence=0.7,
                                     confirmed=False))
        elif row.source == "inferred":
            row.value = value


async def ensure_builtin_templates(db: AsyncSession) -> None:
    """Create the built-in templates once (owner_id NULL)."""
    storage = get_storage()
    for key, st in BUILTIN_STYLES.items():
        exists = (await db.execute(select(Template).where(Template.owner_id.is_(None), Template.name == st["name"])
                                   )).scalars().first()
        if exists:
            continue
        base, spec = await asyncio.to_thread(build_builtin, key)
        tid = uuid.uuid4()
        base_key = f"templates/{tid}/base.pptx"
        await storage.put(base_key, base)
        previews = await render_previews(tid, base, spec)
        db.add(Template(id=tid, owner_id=None, name=st["name"], mode="builtin", base_storage_key=base_key, spec=spec,
                        preview_keys=previews, is_shared=True))
        await db.flush()

