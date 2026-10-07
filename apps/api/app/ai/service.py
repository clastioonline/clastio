"""AIService: task routing, provider fallback, retries, caching and usage/cost accounting."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, update

from app.ai import budget
from app.ai.anthropic_provider import AnthropicProvider
from app.ai.base import (
    AIError,
    AIRequest,
    ChatMessage,
    Effort,
    ImageInput,
    ImageResult,
    T,
    Tier,
    Usage,
)
from app.ai.capacity import provider_capacity
from app.ai.compatible_provider import CompatibleProvider
from app.ai.gemini_provider import GeminiProvider
from app.ai.offline_provider import OfflineProvider
from app.ai.openai_provider import OpenAIProvider
from app.ai.openrouter_provider import OPENROUTER_MODELS, OpenRouterProvider
from app.ai.pricing import cost_usd
from app.core.config import get_settings
from app.core.logging import log

logger = logging.getLogger("ai")

# Same-tier defaults used as fallbacks when the configured provider is unavailable or failing.
PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "anthropic": {
        "planning": "claude-sonnet-4-6", "content": "claude-sonnet-5", "fast": "claude-haiku-4-5",
        "vision": "claude-sonnet-5", "qc": "claude-haiku-4-5",
    },
    "openai": {
        "planning": "gpt-5.5", "content": "gpt-4o-mini", "fast": "gpt-5.4-nano", "vision": "gpt-5.4-mini",
        "qc": "gpt-5.4-nano", "embedding": "text-embedding-3-small", "image": "gpt-image-1-mini",
        "video": "sora-2", "reflection": "gpt-4o-mini",
    },
    "gemini": {
        "ingestion": "gemini-3.5-flash", "planning": "gemini-2.5-pro", "content": "gemini-3.5-flash", "fast": "gemini-3.1-flash-lite",
        "vision": "gemini-3.5-flash", "qc": "gemini-3.1-flash-lite", "embedding": "gemini-embedding-001",
        "image": "gemini-2.5-flash-image", "video": "veo-3.0-fast-generate-001",
    },
}
PROVIDER_DEFAULTS["groq"] = {"fast": "llama-3.3-70b-versatile"}
PROVIDER_DEFAULTS["perplexity"] = {"search": "sonar"}
PROVIDER_DEFAULTS["openrouter"] = OPENROUTER_MODELS
PROVIDER_ORDER = ["openrouter", "anthropic", "openai", "gemini", "groq", "perplexity"]


@dataclass
class Route:
    provider: str
    model: str


class _LRU:
    def __init__(self, size: int = 512):
        self.size = size
        self.data: OrderedDict[str, Any] = OrderedDict()
        self.expires: dict[str, float] = {}

    def get(self, key: str) -> Any:
        if key in self.data and self.expires.get(key, 0) <= time.monotonic():
            self.data.pop(key, None)
            self.expires.pop(key, None)
        if key in self.data:
            self.data.move_to_end(key)
            return self.data[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.expires[key] = time.monotonic() + 86400
        self.data.move_to_end(key)
        while len(self.data) > self.size:
            old_key, _ = self.data.popitem(last=False)
            self.expires.pop(old_key, None)


class CircuitBreaker:
    """Per-provider breaker: after FAILURE_THRESHOLD consecutive failures a provider is skipped for OPEN_SECONDS,
    then one trial call is allowed (half-open). State is mirrored to provider_health for the admin console, and
    breakers opened by another process are respected once that table is re-read."""

    FAILURE_THRESHOLD = 5
    OPEN_SECONDS = 60

    def __init__(self) -> None:
        self.failures: dict[str, int] = {}
        self.open_until: dict[str, float] = {}

    def is_open(self, provider: str) -> bool:
        return self.open_until.get(provider, 0) > time.time()

    def success(self, provider: str) -> None:
        self.failures[provider] = 0
        self.open_until.pop(provider, None)

    def failure(self, provider: str) -> bool:
        """Count a failure; returns True if this failure opened the breaker."""
        n = self.failures.get(provider, 0) + 1
        self.failures[provider] = n
        if n >= self.FAILURE_THRESHOLD and not self.is_open(provider):
            self.open_until[provider] = time.time() + self.OPEN_SECONDS
            self.failures[provider] = self.FAILURE_THRESHOLD - 1  # half-open: one more failure re-opens
            return True
        return False


class AIService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.providers = {
            "openrouter": OpenRouterProvider(),
            "anthropic": AnthropicProvider(),
            "openai": OpenAIProvider(),
            "gemini": GeminiProvider(),
            "groq": CompatibleProvider("groq", self.settings.groq_api_key, "https://api.groq.com/openai/v1"),
            "perplexity": CompatibleProvider("perplexity", self.settings.perplexity_api_key, "https://api.perplexity.ai"),
            "offline": OfflineProvider(),
        }
        self._sem = asyncio.Semaphore(self.settings.ai_max_concurrency)
        self._cache = _LRU()
        self._result_cache = None
        if self.settings.redis_url:
            import redis.asyncio as redis
            self._result_cache = redis.from_url(self.settings.redis_url, socket_timeout=1, socket_connect_timeout=1)
        self._overrides: dict[str, Any] = {}
        self._overrides_at = 0.0
        self.breaker = CircuitBreaker()

    # ------------------------------------------------------------------ routing

    @property
    def live_providers(self) -> list[str]:
        if self.settings.ai_offline_mode:
            return []
        order = ["openrouter"] if self.settings.openrouter_only else PROVIDER_ORDER
        return [p for p in order if self.providers[p].available()]

    @property
    def mode(self) -> str:
        return "offline" if self.settings.ai_offline_mode else "live" if self.live_providers else "unavailable"

    async def _load_overrides(self) -> dict[str, Any]:
        if time.monotonic() - self._overrides_at < 30:
            return self._overrides
        try:
            from app.services.settings import get_app_settings

            self._overrides = await get_app_settings(["model_routing", "ai_pricing"])
            await self._load_breakers()
        except Exception:  # DB not ready (e.g. CLI usage) - keep env defaults
            self._overrides = {}
        self._overrides_at = time.monotonic()
        return self._overrides

    async def _load_breakers(self) -> None:
        from sqlalchemy import select

        from app.core.db import get_sessionmaker
        from app.models import ProviderHealth

        async with get_sessionmaker()() as s:
            for row in (await s.execute(select(ProviderHealth))).scalars().all():
                if row.open_until and row.open_until.timestamp() > self.breaker.open_until.get(row.provider, 0):
                    self.breaker.open_until[row.provider] = row.open_until.timestamp()

    def _configured(self, tier: Tier, overrides: dict[str, Any]) -> str:
        routing = overrides.get("model_routing") or {}
        if tier in routing:
            return routing[tier]
        return getattr(self.settings, f"model_{tier}")

    async def routes(self, tier: Tier) -> list[Route]:
        overrides = await self._load_overrides()
        chain: list[Route] = []
        configured = self._configured(tier, overrides)
        if ":" in configured:
            prov, model = configured.split(":", 1)
            if prov in self.live_providers:
                chain.append(Route(prov, model))
        for prov in self.live_providers:
            model = PROVIDER_DEFAULTS.get(prov, {}).get(tier)
            if model and not any(r.provider == prov for r in chain):
                chain.append(Route(prov, model))
        healthy = [r for r in chain if not self.breaker.is_open(r.provider)]
        return [Route("offline", "offline")] if self.settings.ai_offline_mode else healthy[:2]

    # ------------------------------------------------------------------ accounting

    async def _record(self, *, task: str, route: Route, usage: Usage, latency_ms: int, success: bool,
                      owner_id: uuid.UUID | None, job_id: uuid.UUID | None, error: str | None = None,
                      prompt_version: str | None = None, recorded_cost: float | None = None,
                      reservation_id: uuid.UUID | None = None) -> float:
        overrides = await self._load_overrides()
        cost = recorded_cost if recorded_cost is not None else cost_usd(route.model, usage, overrides.get("ai_pricing"))
        job_id = budget.job_context(job_id)
        log(logger, logging.INFO if success else logging.WARNING, "ai_call", task=task, provider=route.provider,
            model=route.model, in_tok=usage.input_tokens, out_tok=usage.output_tokens,
            cached=usage.cached_tokens, cost_usd=cost, latency_ms=latency_ms, success=success, error=error)
        opened = False
        if route.provider != "offline":
            if success:
                self.breaker.success(route.provider)
            else:
                opened = self.breaker.failure(route.provider)
        try:
            from sqlalchemy.dialects.postgresql import insert

            from app.core.db import get_sessionmaker, utcnow
            from app.core.logging import request_id_var
            from app.models import AICallReservation, AIUsage, GenerationJob, ProviderHealth

            async with get_sessionmaker()() as s:
                reservation = await s.get(AICallReservation, reservation_id, with_for_update=True) if reservation_id else None
                if reservation:
                    owner_id = owner_id or reservation.owner_id
                    if reservation.charged_usd is not None:
                        cost = float(reservation.charged_usd)
                entry = AIUsage(owner_id=owner_id, job_id=job_id, task=task, provider=route.provider,
                              model=route.model, prompt_version=prompt_version,
                              input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                              cached_tokens=usage.cached_tokens, images=usage.images, cost_usd=cost,
                              latency_ms=latency_ms, success=success, error=(error or "")[:2000] or None,
                              request_id=request_id_var.get(), error_code=_error_code(error) if error else None)
                s.add(entry)
                if reservation:
                    await s.flush()
                    reservation.usage_id = entry.id
                if route.provider != "offline":
                    open_until = self.breaker.open_until.get(route.provider)
                    values = {"failures": self.breaker.failures.get(route.provider, 0), "updated_at": utcnow(),
                              "open_until": datetime.fromtimestamp(open_until, UTC) if open_until else None}
                    if not success:
                        values["last_error"] = (error or "")[:1000]
                    stmt = insert(ProviderHealth).values(provider=route.provider, successes=int(success),
                                                         avg_latency_ms=float(latency_ms), **values)
                    await s.execute(stmt.on_conflict_do_update(index_elements=["provider"], set_={
                        **values, "successes": ProviderHealth.successes + int(success),
                        "avg_latency_ms": (func.coalesce(ProviderHealth.avg_latency_ms, latency_ms) * 0.9
                                           + latency_ms * 0.1)}))
                if opened:
                    from app.services.events import security_event

                    security_event(s, "provider_circuit_open", severity="warning", provider=route.provider,
                                   error=(error or "")[:300])
                if job_id and cost:
                    await s.execute(update(GenerationJob).where(GenerationJob.id == job_id)
                                    .values(cost_usd=GenerationJob.cost_usd + cost))
                await s.commit()
        except Exception as e:  # accounting must never break generation
            log(logger, logging.WARNING, "ai_usage_record_failed", error=str(e))
        return cost

    # ------------------------------------------------------------------ public API

    @staticmethod
    def _cache_key(*parts: Any) -> str:
        return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()

    async def _execute(self, *, route, task, owner_id, job_id, call, input_bytes=0,
                       output_tokens=0, prompt_version=None):
        # Acquire capacity before reserving so queued requests hold no funds.
        async with self._sem, provider_capacity(
            self._result_cache if route.provider != "offline" else None,
            limit=self.settings.ai_global_concurrency, wait_s=self.settings.ai_request_timeout_s,
        ):
            ticket = await budget.reserve(provider=route.provider, model=route.model, task=task,
                owner_id=owner_id, job_id=job_id, input_bytes=input_bytes, output_tokens=output_tokens)
            start = time.monotonic()
            try:
                result = await call()
            except BaseException as exc:
                usage = exc.usage if isinstance(exc, AIError) else None
                cost = await budget.settle(ticket, usage, False)
                await self._record(task=task, route=route, usage=usage or Usage(reported=False), success=False,
                    latency_ms=int((time.monotonic() - start) * 1000), owner_id=owner_id, job_id=job_id,
                    error=str(exc), prompt_version=prompt_version, recorded_cost=cost, reservation_id=ticket)
                if isinstance(exc, AIError) and ticket and (usage is None or not usage.reported):
                    exc.retryable = False  # Never repeat a request with an unknown charge.
                raise
            usage = result[1] if isinstance(result, tuple) else result.usage
            cost = await budget.settle(ticket, usage, True)
            await self._record(task=task, route=route, usage=usage, success=True,
                latency_ms=int((time.monotonic() - start) * 1000), owner_id=owner_id, job_id=job_id,
                prompt_version=prompt_version, recorded_cost=cost, reservation_id=ticket)
            return result

    @staticmethod
    def _input_bytes(req, schema=None):
        # Byte count deliberately overestimates text tokens, and includes image payloads/schema.
        return len(req.system.encode()) + sum(len(m.content.encode()) + sum(len(i.data) for i in m.images)
            for m in req.messages) + (len(json.dumps(schema.model_json_schema()).encode()) if schema else 0)

    async def _cached_result(self, key: str):
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        if self._result_cache is not None:
            try:
                raw = await self._result_cache.get("ai:result:v1:" + key)
                if raw is not None:
                    hit = json.loads(raw)
                    self._cache.set(key, hit)
                    return hit
            except Exception:
                logger.warning("AI result cache unavailable; continuing without shared cache")
        return None

    async def _store_result(self, key: str, value: dict) -> None:
        self._cache.set(key, value)
        if self._result_cache is not None:
            try:
                await self._result_cache.set("ai:result:v1:" + key, json.dumps(value), ex=86400)
            except Exception:
                logger.warning("AI result cache write unavailable")

    async def structured(self, *, task: str, tier: Tier, system: str, prompt: str, schema: type[T],
                         images: list[ImageInput] | None = None, effort: Effort = "medium",
                         max_tokens: int = 16000, owner_id: uuid.UUID | None = None,
                         job_id: uuid.UUID | None = None, offline_context: dict[str, Any] | None = None,
                         prompt_version: str | None = None, cache: bool = False) -> T:
        req = AIRequest(task=task, system=system, messages=[ChatMessage("user", prompt, images or [])],
                        max_tokens=max_tokens, effort=effort, offline_context=offline_context or {})
        last = None
        for route in await self.routes(tier):
            key = self._cache_key(owner_id, task, route.provider, route.model, system, prompt,
                schema.model_json_schema(), prompt_version, effort, max_tokens, offline_context,
                [(i.media_type, hashlib.sha256(i.data).hexdigest()) for i in images or []]) if cache and owner_id else None
            if key and (hit := await self._cached_result(key)) is not None:
                try:
                    return schema.model_validate(hit)
                except (ValueError, TypeError):
                    logger.warning("Ignoring incompatible AI cache entry")
            try:
                result = await self._execute(route=route, task=task, owner_id=owner_id, job_id=job_id,
                    input_bytes=self._input_bytes(req, schema), output_tokens=max_tokens,
                    prompt_version=prompt_version,
                    call=lambda route=route: self.providers[route.provider].generate_structured(route.model, req, schema))
                if key:
                    await self._store_result(key, result.data.model_dump())
                return result.data
            except AIError as exc:
                if not exc.retryable:
                    raise
                last = exc
        raise AIError(f"AI generation unavailable for {task}: {last}", retryable=False)

    async def transcribe(self, audio: bytes, *, filename: str, owner_id: uuid.UUID,
                         job_id: uuid.UUID | None = None) -> str:
        from app.ai.base import TextResult

        candidates = [name for name in ("groq", "openai")
                      if name in self.live_providers and not self.breaker.is_open(name)]
        if not candidates:
            raise AIError("Voice transcription needs a healthy Groq or OpenAI provider", retryable=False)
        provider = candidates[0]
        model = "whisper-large-v3-turbo" if provider == "groq" else "whisper-1"
        route = Route(provider, model)

        async def call():
            adapter = self.providers[provider]
            try:
                result = await adapter._client.audio.transcriptions.create(
                    model=model, file=(filename, audio), response_format="json")
            except Exception as exc:
                raise AIError("Voice transcription failed", provider=provider) from exc
            # Transcription APIs do not supply token usage; retain the approved reservation ceiling.
            return TextResult(result.text, Usage(reported=False), model, provider)

        result = await self._execute(route=route, task="transcription", owner_id=owner_id, job_id=job_id,
                                     input_bytes=len(audio), output_tokens=2000, call=call)
        return result.text

    async def text(self, *, task: str, tier: Tier, system: str, messages: list[ChatMessage],
                   effort: Effort = "medium", max_tokens: int = 8000, owner_id: uuid.UUID | None = None,
                   job_id: uuid.UUID | None = None, offline_context: dict[str, Any] | None = None) -> str:
        req = AIRequest(task=task, system=system, messages=messages, max_tokens=max_tokens, effort=effort,
                        offline_context=offline_context or {})
        last = None
        for route in await self.routes(tier):
            try:
                result = await self._execute(route=route, task=task, owner_id=owner_id, job_id=job_id,
                    input_bytes=self._input_bytes(req), output_tokens=max_tokens,
                    call=lambda route=route: self.providers[route.provider].generate_text(route.model, req))
                return result.text
            except AIError as exc:
                if not exc.retryable:
                    raise
                last = exc
        raise AIError(f"AI generation unavailable for {task}: {last}", retryable=False)

    async def stream(self, *, task: str, tier: Tier, system: str, messages: list[ChatMessage],
                     effort: Effort = "low", max_tokens: int = 4000, owner_id: uuid.UUID | None = None,
                     job_id: uuid.UUID | None = None,
                     offline_context: dict[str, Any] | None = None) -> AsyncIterator[str]:
        req = AIRequest(task=task, system=system, messages=messages, max_tokens=max_tokens, effort=effort,
                        offline_context=offline_context or {})
        # No automatic stream restart: replay after a partial answer can duplicate charges/content.
        routes = await self.routes(tier)
        if not routes:
            raise AIError("AI chat is temporarily unavailable", retryable=False)
        route = routes[0]
        async with self._sem, provider_capacity(
            self._result_cache if route.provider != "offline" else None,
            limit=self.settings.ai_global_concurrency, wait_s=self.settings.ai_request_timeout_s,
        ):
            ticket = await budget.reserve(provider=route.provider, model=route.model, task=task,
                owner_id=owner_id, job_id=job_id, input_bytes=self._input_bytes(req), output_tokens=max_tokens)
            usage = Usage(reported=False)
            start = time.monotonic()
            success = False
            error = None
            try:
                async for chunk in self.providers[route.provider].stream_text(route.model, req, usage):
                    yield chunk
                success = True
            except BaseException as exc:
                error = str(exc)
                usage = exc.usage if isinstance(exc, AIError) and exc.usage else Usage(reported=False)
                if isinstance(exc, AIError):
                    exc.retryable = False
                raise
            finally:
                cost = await budget.settle(ticket, usage, success)
                await self._record(task=task, route=route, usage=usage, success=success, error=error,
                    latency_ms=int((time.monotonic() - start) * 1000), owner_id=owner_id,
                    job_id=job_id, recorded_cost=cost, reservation_id=ticket)

    async def embed(self, texts: list[str], owner_id: uuid.UUID | None = None) -> list[list[float]]:
        if not texts:
            return []
        dim = self.settings.embedding_dim
        for route in await self.routes("embedding"):
            try:
                vectors, usage = await self._execute(route=route, task="embedding", owner_id=owner_id,
                    job_id=None, input_bytes=sum(len(t.encode()) for t in texts),
                    call=lambda route=route: self.providers[route.provider].generate_embedding(route.model, texts, dim))
                return [list(v)[:dim] + [0.0] * max(0, dim - len(v)) for v in vectors]
            except AIError as exc:
                if not exc.retryable:
                    raise
        raise AIError("Embedding failed", retryable=False)

    async def _media_routes(self, tier: Tier, model: str | None) -> list[Route]:
        chain = [r for r in await self.routes(tier) if r.provider != "offline"]
        if model and ":" in model:
            prov, name = model.split(":", 1)
            if prov in self.live_providers and not self.breaker.is_open(prov):
                chain = [Route(prov, name)] + [r for r in chain if (r.provider, r.model) != (prov, name)]
        return chain[:2]

    async def image(self, prompt: str, size: str = "1536x1024", owner_id: uuid.UUID | None = None,
                    job_id: uuid.UUID | None = None, model: str | None = None,
                    task: str = "image") -> ImageResult | None:
        return await self._media(task, "image", model, owner_id, job_id,
            lambda p, m: p.generate_image(m, prompt, size), len(prompt.encode()))

    async def video(self, prompt: str, seconds: int = 4, aspect: str = "16:9", owner_id: uuid.UUID | None = None,
                    job_id: uuid.UUID | None = None, model: str | None = None) -> ImageResult | None:
        return await self._media("video", "video", model, owner_id, job_id,
            lambda p, m: p.generate_video(m, prompt, seconds, aspect), len(prompt.encode()))

    async def _media(self, task, tier, model, owner_id, job_id, call, input_bytes):
        if self.settings.ai_offline_mode:
            return None
        for route in await self._media_routes(tier, model):
            try:
                return await self._execute(route=route, task=task, owner_id=owner_id, job_id=job_id,
                    input_bytes=input_bytes, call=lambda route=route: call(self.providers[route.provider], route.model))
            except AIError as exc:
                if not exc.retryable:
                    raise
        raise AIError(f"{tier} generation unavailable", retryable=False)


def _error_code(error: str) -> str:
    e = error.lower()
    for code, needles in (("timeout", ("timeout", "timed out")), ("rate_limited", ("429", "rate limit", "overloaded")),
                          ("auth", ("401", "invalid api key", "authentication")), ("refused", ("refus", "declin")),
                          ("invalid_output", ("validation", "truncated", "json")), ("server", ("500", "502", "503"))):
        if any(n in e for n in needles):
            return code
    return "error"


_service: AIService | None = None


def get_ai() -> AIService:
    global _service
    if _service is None:
        import app.generation.offline  # noqa: F401  (registers offline generators)

        _service = AIService()
    return _service


def reset_ai() -> None:
    global _service
    _service = None
