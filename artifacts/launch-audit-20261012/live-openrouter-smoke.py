"""Explicitly authorized two-request synthetic live provider check; no app artifacts."""
import asyncio
import json
import logging
import re
import uuid
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import select

from app.ai import budget
from app.ai.base import AIError, AIRequest, ChatMessage
from app.ai.service import AIService
from app.core.db import get_sessionmaker
from app.core.logging import job_id_var, request_id_var, user_id_var
from app.generation.lesson_workflow import LessonMaterial, SlideBatch
from app.models import AICallReservation, AIUsage

logging.disable(logging.CRITICAL)
VERSION = "launch-smoke-" + uuid.uuid4().hex[:12]
MAX_OUTPUT = 4000
EXPECTED = {"planning": "anthropic/claude-sonnet-4.6", "content": "openai/gpt-5.4-mini"}
BYTE_CAPS = {"planning": 6500, "content": 14000}
SYSTEM = ("Return only the requested strict JSON schema. Use brief, complete synthetic classroom content. "
          "No research, invented source references or official curriculum claims. Only supplied objective code SYNTH-1.")
TEACHING_PROMPT = (
    "Synthetic Grade 6 mathematics: adding proper fractions with equal denominators. "
    "Outcome SYNTH-1: add fractions with the same denominator. Return LessonMaterial, exactly 8 numbered "
    "blocks, each with a title and purpose. Keep every content field below 20 words, optional unused strings empty "
    "and source_references empty. Blocks: 1 opening topic; 2 numerator/denominator prerequisite; "
    "3 definition of addition with equal denominators; 4 fully worked 1/4+2/4=3/4; "
    "5 misconception: denominators do not get added; 6 guided question 1/5+3/5, expected_answer 4/5; "
    "7 independent question 2/7+3/7, expected_answer 5/7; 8 exit question 1/8+2/8, expected_answer 3/8. "
    "Every non-cover block needs explanation, example or student question. All student questions need answers. "
    "Lesson plan lecture_number 1, duration_minutes 20, concise objective and success criterion; "
    "four phases starter/main/activity/plenary taking 3/9/5/3 minutes; one question, one misconception, "
    "brief differentiation in each field, resources [], safety_notes null, homework one fraction problem "
    "estimated_minutes 2, exit_ticket one question."
)


def admission_bytes(task, prompt, schema):
    return AIService._input_bytes(AIRequest(task, SYSTEM, [ChatMessage("user", prompt)],
                                           max_tokens=MAX_OUTPUT, effort="low"), schema)


def estimate(plan_bytes, content_bytes):
    # UTF-8 bytes overestimate text tokens; allow 512 further framing tokens per request.
    # Sonnet: highest currently quoted +10% regional/cache-write rate and output rate.
    return ((plan_bytes + 512) * 4.125 + MAX_OUTPUT * 16.5
            + (content_bytes + 512) * 0.75 + MAX_OUTPUT * 4.5) / 1_000_000


def check(ok, message):
    if not ok:
        raise AssertionError(message)


def quality_material(material):
    checks = {
        "schema_valid": True,
        "eight_numbered_blocks": [b.number for b in material.blocks] == list(range(1, 9)),
        "titles_and_purposes": all(b.title.strip() and b.purpose.strip() for b in material.blocks),
        "definition_present": any(b.definition.strip() for b in material.blocks),
        "worked_example_present": any("3/4" in b.worked_example for b in material.blocks),
        "all_questions_have_answers": all(not b.student_question.strip() or b.expected_answer.strip()
                                           for b in material.blocks),
        "guided_answer_correct": len(material.blocks) == 8 and "4/5" in material.blocks[5].expected_answer,
        "independent_answer_correct": len(material.blocks) == 8 and "5/7" in material.blocks[6].expected_answer,
        "exit_answer_correct": len(material.blocks) == 8 and "3/8" in material.blocks[7].expected_answer,
        "no_invented_references": all(not b.source_references for b in material.blocks),
        "phase_minutes_match": sum(p.minutes for p in material.lesson_plan.phases) == 20,
        "no_invented_codes": set(re.findall(r"\b[A-Z]{2,}[-_]\d+\b", material.model_dump_json())) <= {"SYNTH-1"},
    }
    return checks


def quality_batch(batch):
    checks = {
        "schema_valid": True,
        "three_numbered_slides": [s.number for s in batch.slides] == [4, 5, 6],
        "layouts_match_plan": [s.layout for s in batch.slides] == ["worked_example", "concept", "quiz"],
        "supplied_objective_only": all(s.outcome_codes == ["SYNTH-1"] for s in batch.slides),
        "titles_and_purposes": all(s.title.strip() and s.purpose.strip() for s in batch.slides),
        "no_images_or_assets": all(s.visual.kind == "none" and s.asset_id is None and
                                   s.visual.source_image_key is None for s in batch.slides),
        "no_invented_references": all(not s.sources for s in batch.slides),
        "worked_example_correct": bool(batch.slides) and "3/4" in batch.slides[0].model_dump_json(),
        "independent_answer_in_notes": len(batch.slides) == 3 and "5/7" in batch.slides[2].speaker_notes,
        "student_text_word_limit": all(sum(len(text.split()) for text in
            [s.title, s.subtitle or "", s.question or "", *[b.text for b in s.bullets],
             *[x for step in s.steps for x in [step.label, step.detail]]]) <= 120 for s in batch.slides),
    }
    return checks


async def main():
    job_id_var.set(None)
    user_id_var.set(None)
    request_id_var.set(VERSION)
    report = {"run": VERSION, "started_at": datetime.now(UTC).isoformat(),
              "synthetic_only": True, "user_artifacts_saved": False, "settings_changed": False,
              "max_upstream_requests": 2, "output_tokens_per_call": MAX_OUTPUT,
              "upstream_requests": 0, "calls": [], "status": "preflight"}
    service = AIService()
    provider = service.providers["openrouter"]
    upstream_meta = []
    try:
        check(service.mode == "live" and service.settings.openrouter_only and provider.available(),
              "Runtime is not the approved live OpenRouter configuration")
        check(provider._client.max_retries == 0, "SDK retries must be disabled")
        approved = {}
        for tier in EXPECTED:
            routes = await service.routes(tier)
            check(bool(routes) and routes[0].provider == "openrouter" and routes[0].model == EXPECTED[tier],
                  "Primary model route changed; no paid call allowed")
            approved[tier] = routes[0]
        async with get_sessionmaker()() as db:
            policy, cards = await budget.config(db)
        check(policy.live_enabled, "Live budget is disabled")
        holds = [budget.RateCard.model_validate(cards[f"openrouter:{model}"]).ceiling_usd
                 for model in EXPECTED.values()]
        check(sum(holds) <= 1.05, "Existing fixed holds exceed approved maximum")
        check(MAX_OUTPUT <= policy.max_output_tokens, "Output cap exceeds policy")
        report["fixed_existing_reservations_usd"] = holds
        report["models"] = EXPECTED
        report["conservative_estimate_usd"] = round(estimate(BYTE_CAPS["planning"], BYTE_CAPS["content"]), 8)
        check(report["conservative_estimate_usd"] <= .15, "Estimated spending exceeds approval")
        plan_size = admission_bytes("lesson_teaching", TEACHING_PROMPT, LessonMaterial)
        check(plan_size <= BYTE_CAPS["planning"] and plan_size <= policy.max_input_bytes,
              "Lesson material input exceeds approved cap")

        async def single_route(tier):
            check(tier in approved, "Unapproved task tier")
            return [approved[tier]]
        service.routes = single_route

        async def guard_request(request):
            check(report["upstream_requests"] < 2, "Maximum two upstream requests reached")
            check(request.method == "POST" and request.url.host == "openrouter.ai" and
                  request.url.path == "/api/v1/chat/completions", "Unapproved upstream endpoint")
            body = json.loads(request.content)
            expected_model = list(EXPECTED.values())[report["upstream_requests"]]
            check(body["model"] == expected_model and body["max_tokens"] == MAX_OUTPUT,
                  "Upstream model or token allowance changed")
            check(body["response_format"]["json_schema"]["strict"] is True,
                  "Strict structured output required")
            report["upstream_requests"] += 1

        async def capture_response(response):
            await response.aread()
            metadata = {"http_status": response.status_code}
            try:
                body = response.json()
                metadata["finish_reason"] = (body.get("choices") or [{}])[0].get("finish_reason")
                metadata["reported_model"] = body.get("model")
            except (ValueError, TypeError):
                metadata["response_json"] = False
            upstream_meta.append(metadata)

        provider._client._client.event_hooks["request"].append(guard_request)
        provider._client._client.event_hooks["response"].append(capture_response)
        original_generate = provider.generate_structured
        async def capture_result(model, req, schema):
            result = await original_generate(model, req, schema)
            report["calls"][-1]["usage"] = asdict(result.usage)
            return result
        provider.generate_structured = capture_result

        report["calls"].append({"task": "lesson_teaching", "schema": "LessonMaterial",
                                "model": EXPECTED["planning"], "input_bytes": plan_size})
        material = await service.structured(task="lesson_teaching", tier="planning", system=SYSTEM,
            prompt=TEACHING_PROMPT, schema=LessonMaterial, max_tokens=MAX_OUTPUT, effort="low",
            owner_id=None, job_id=None, cache=False, prompt_version=VERSION)
        report["calls"][-1]["quality"] = quality_material(material)
        check(all(report["calls"][-1]["quality"].values()), "Teaching material quality assertion failed")

        batch_prompt = json.dumps({"grade": 6, "subject": "Mathematics",
            "outcomes": [{"code": "SYNTH-1", "description": "Add fractions with equal denominators"}],
            "approved_content": [b.model_dump() for b in material.blocks[3:6]],
            "layout_plan": [{"number": 4, "layout": "worked_example"},
                            {"number": 5, "layout": "concept"}, {"number": 6, "layout": "quiz"}]},
            separators=(",", ":")) + (
            "\nReturn exactly these three slides with these layouts and outcome_codes [\"SYNTH-1\"]. "
            "Use brief complete text. Slide4 fully solves 1/4+2/4=3/4; slide5 explains the fixed denominator; "
            "slide6 asks 2/7+3/7 and puts expected answer 5/7 in speaker_notes. "
            "Every visual.kind must be none; all assets/source_image_key null, sources [], "
            "manual_objects {}, other unused fields null or empty. No external source or media calls."
        )
        content_size = admission_bytes("lesson_deck_batch", batch_prompt, SlideBatch)
        report["actual_input_conservative_estimate_usd"] = round(estimate(plan_size, content_size), 8)
        check(content_size <= BYTE_CAPS["content"] and content_size <= policy.max_input_bytes and
              estimate(plan_size, content_size) <= .15, "Batch request exceeds approved cost/input cap")
        report["calls"].append({"task": "lesson_deck_batch", "schema": "SlideBatch",
                                "model": EXPECTED["content"], "input_bytes": content_size})
        batch = await service.structured(task="lesson_deck_batch", tier="content", system=SYSTEM,
            prompt=batch_prompt, schema=SlideBatch, max_tokens=MAX_OUTPUT, effort="low",
            owner_id=None, job_id=None, cache=False, prompt_version=VERSION)
        report["calls"][-1]["quality"] = quality_batch(batch)
        check(all(report["calls"][-1]["quality"].values()), "Slide batch quality assertion failed")
        report["status"] = "passed"
    except Exception as exc:
        report["status"] = "stopped_after_failure"
        report["error_type"] = type(exc).__name__
        # Whitelist local assertions and generic adapter classifications, never raw provider errors.
        report["error"] = (str(exc) if isinstance(exc, AssertionError) else
            "Response truncated" if "Response truncated" in str(exc) else
            "Provider request or guarded admission failed; no further request attempted")
    finally:
        report["upstream_metadata"] = upstream_meta
        try:
            async with get_sessionmaker()() as db:
                rows = (await db.execute(select(AICallReservation).join(AIUsage,
                    AICallReservation.usage_id == AIUsage.id).where(AIUsage.prompt_version == VERSION))).scalars().all()
            report["operational_ledger"] = [{"task": r.task, "model": r.model, "status": r.status,
                "reserved_usd": float(r.reserved_usd),
                "charged_usd": float(r.charged_usd) if r.charged_usd is not None else None,
                "success": r.success} for r in rows]
            report["actual_cost_usd"] = round(sum(float(r.charged_usd or 0) for r in rows), 8)
        except Exception:
            report["ledger_read"] = "unavailable"
        await provider._client.close()
        report["finished_at"] = datetime.now(UTC).isoformat()
        print(json.dumps(report, indent=2, sort_keys=True))


asyncio.run(main())
