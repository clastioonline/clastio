"""Explicitly authorized, bounded live review. Run in the review container, never production.

Requires --execute; reads OPENAI_API_KEY without printing or copying it. Paid generation
is disabled again in finally. Artifacts contain generated content and usage, never keys.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import uuid
from datetime import UTC, datetime
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "apps/web/e2e/screenshots/live-openai-review"
MODEL = "gpt-4.1-mini-2025-04-14"


def configure():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    if not args.execute:
        parser.error("Paid generation requires --execute and prior user authorization.")
    OUT = args.out
    if "pptgenie_review" not in os.environ.get("DATABASE_URL", ""):
        raise RuntimeError("This script only runs against the local pptgenie_review database")
    key = dotenv_values(ROOT / ".env").get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Save OPENAI_API_KEY in the root .env first")
    os.environ.update(OPENAI_API_KEY=key, OPENAI_BASE_URL="https://api.openai.com/v1",
        ANTHROPIC_API_KEY="", GEMINI_API_KEY="", AI_OFFLINE_MODE="false", ENVIRONMENT="development",
        RUN_JOBS_INLINE="true", OPENVERSE_ENABLED="false", AI_MAX_CONCURRENCY="1")


async def main():
    import httpx
    from sqlalchemy import select

    import app.jobs.handlers  # noqa: F401
    from app.ai.budget import BudgetPolicy, dashboard
    from app.ai.service import get_ai
    from app.core.db import get_sessionmaker
    from app.main import app
    from app.models import AICallReservation, AppSetting
    from app.services.settings import set_setting

    ai = get_ai()
    # Only the explicitly authorized provider can be contacted by this review.
    ai.providers = {k: v for k, v in ai.providers.items() if k in ("openai", "offline")}
    ai.settings.anthropic_api_key = None
    ai.settings.gemini_api_key = None
    # Availability checks iterate these adapters, so retain inert adapter objects.
    from app.ai.anthropic_provider import AnthropicProvider
    from app.ai.gemini_provider import GeminiProvider
    ai.providers.update(anthropic=AnthropicProvider(), gemini=GeminiProvider())
    ai.providers["anthropic"]._client = None
    ai.providers["gemini"]._client = None

    keys = ["ai_budget", "ai_rate_cards", "model_routing", "feature_flags"]
    async with get_sessionmaker()() as db:
        saved = {r.key: r.value for r in (await db.execute(select(AppSetting).where(AppSetting.key.in_(keys)))).scalars()}
    # Ceiling covers <=120k input bytes plus <=24k output tokens at verified prices.
    policy = BudgetPolicy(live_enabled=True, daily_usd=.95, monthly_usd=.95,
        user_monthly_usd=.95, job_usd=.95, call_usd=.1, max_calls_per_job=20,
        max_input_bytes=120000, max_output_tokens=24000)
    cards = {f"openai:{MODEL}": {"input": .4, "output": 1.6, "cached": .1, "cache_write": .4,
        "ceiling_usd": .1, "source": "https://developers.openai.com/api/docs/models/gpt-4.1-mini"},
        "openai:text-embedding-3-small": {"input": .02, "output": 0, "cached": .02, "cache_write": .02,
        "ceiling_usd": .003, "source": "https://developers.openai.com/api/docs/models/text-embedding-3-small"}}
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"started_at": datetime.now(UTC).isoformat(), "model": MODEL, "authorized_budget_usd": 1,
              "admission_limit_usd": .95, "stages": []}
    owner = None
    try:
        await set_setting("ai_rate_cards", cards)
        await set_setting("model_routing", {**{t: f"openai:{MODEL}" for t in
            ["planning", "content", "fast", "vision", "qc"]}, "embedding": "openai:text-embedding-3-small"})
        await set_setting("feature_flags", {"ai_images": False, "openverse": False, "vision_qc": False})
        await set_setting("ai_budget", policy.model_dump())
        ai._overrides_at = 0
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost:3008",
                                     timeout=600) as client:
            async def request(method, path, **kwargs):
                response = await client.request(method, "/api/v1" + path, **kwargs)
                if not response.is_success:
                    raise RuntimeError(f"{method} {path}: HTTP {response.status_code}: {response.text[:500]}")
                return response.json()

            user = await request("POST", "/auth/signup", json={"email": f"live-review-{uuid.uuid4().hex[:8]}@example.com",
                "password": secrets.token_urlsafe(24), "name": "Grade 1 Live Review", "accept_terms": True})
            owner = uuid.UUID(user["user"]["id"])
            client.headers["Authorization"] = "Bearer " + user["token"]
            await request("PUT", "/me/profile", json={"curriculum": "american", "subjects": ["Mathematics"],
                "grades": ["1"], "country": "AE", "class_duration_minutes": 45})
            source = next(ROOT.glob("W02-G01*.pptx"))
            uploaded = await request("POST", "/uploads", data={"kind": "style", "name": "Grade 1 original design"},
                files={"file": (source.name, source.read_bytes(), "application/octet-stream")})
            assert uploaded["file"]["status"] == "ready", uploaded["file"].get("error")
            template = await request("GET", f"/uploads/{uploaded['file']['id']}")
            report["stages"].append("source_template_ready")
            print("Original PowerPoint template ready", flush=True)
            course = await request("POST", "/courses", json={"topic": "Put Together: Addition within 10",
                "grade": "1", "subject": "Mathematics", "num_lectures": 1, "slides_per_lecture": 10,
                "lecture_minutes": 45, "template_id": template["template_id"], "auto_generate": True,
                "outcomes": [{"code": "1.OA.A.1", "text": "Solve putting-together addition problems within 10 using objects and pictures."}],
                "instructions": "Follow the supplied lesson focus: two parts make one whole. Grade 1, ages 6–7. "
                    "Use small numbers within 10, connecting cubes, apples and UAE flag-colour counters. "
                    "Include accurate worked equations, guided practice, a hands-on partner task and an exit ticket. "
                    "Short simple pupil-facing language; full explanations and correct answers in teacher notes. "
                    "Keep all tasks self-contained: no textbook page references or videos. Avoid photos and paid AI images. "
                    "Do not invent a curriculum standard. This lesson introduces addition; subtraction is a later lesson."})
            project = await request("GET", f"/projects/{course['course']['project_id']}")
            (OUT / "project.json").write_text(json.dumps(project, indent=2))
            assert project["course"]["status"] == "ready", project["course"].get("error")
            lesson_id = project["lessons"][0]["id"]
            detail = await request("GET", f"/lessons/{lesson_id}")
            (OUT / "lesson.json").write_text(json.dumps(detail, indent=2))
            assert detail["lesson"]["qc"]["ai_mode"] == "live"
            assert detail["lesson"]["qc"]["visual_status"] == "checked"
            assert len(detail["slides"]) == 10 and all(s["preview"] for s in detail["slides"])
            for ext, link in detail["downloads"].items():
                if ext not in ("pptx", "pdf") or not link:
                    continue
                download = await client.get(link)
                download.raise_for_status()
                (OUT / f"lesson.{ext}").write_bytes(download.content)
            report["lesson_id"] = lesson_id
            report["project_id"] = course["course"]["project_id"]
            report["visual_issues"] = detail["lesson"]["qc"]["visual"]
            report["stages"].append("live_lesson_exported")
            print("Live lesson generated and exported", flush=True)
            doc = await request("POST", "/documents", json={"kind": "worksheet", "lesson_id": lesson_id,
                "num_questions": 6, "difficulty": "easy", "instructions": "Grade 1 pupils aged 6–7. "
                    "Six short self-contained addition questions within 10, including a putting-together word problem. "
                    "Use explicit numbers; do not refer to missing pictures. Include complete correct answers."})
            document = doc["document"]
            if document["status"] != "ready":
                document = await request("GET", f"/documents/{document['id']}")
            assert document["status"] == "ready", document.get("error")
            (OUT / "worksheet.json").write_text(json.dumps(document, indent=2))
            for ext in ("pdf", "docx", "key_pdf", "key_docx"):
                download = await client.get(document["files"][ext])
                download.raise_for_status()
                (OUT / ("answer-key." + ext[4:] if ext.startswith("key_") else "worksheet." + ext)).write_bytes(download.content)
            report["stages"].append("live_worksheet_exported")
            print("Live worksheet and answer key exported", flush=True)
    except Exception as exc:
        # Avoid exposing credential-bearing exceptions. Detailed task status stays in the local app.
        report["error_type"] = type(exc).__name__
        print("Review stopped:", type(exc).__name__, flush=True)
        raise SystemExit(1) from None
    finally:
        policy.live_enabled = False
        await set_setting("ai_budget", policy.model_dump())
        for key in ["model_routing", "feature_flags", "ai_rate_cards"]:
            await set_setting(key, saved.get(key, {}))
        async with get_sessionmaker()() as db:
            calls = (await db.execute(select(AICallReservation).where(AICallReservation.owner_id == owner))).scalars().all() if owner else []
            report["calls"] = [{"task": r.task, "model": r.model, "status": r.status, "success": r.success,
                "charged_usd": float(r.charged_usd) if r.charged_usd is not None else None,
                "reserved_usd": float(r.reserved_usd), "usage": r.usage} for r in calls]
            report["ledger"] = await dashboard(db)
        report["paid_generation_paused"] = True
        (OUT / "report.json").write_text(json.dumps(report, indent=2, default=str))
        print("Paid generation paused; report saved", flush=True)


if __name__ == "__main__":
    configure()
    asyncio.run(main())
