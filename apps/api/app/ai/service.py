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

from app.ai.anthropic_provider import AnthropicProvider
from app.ai.base import (
    AIError,
    AIRefusal,
    AIRequest,
    ChatMessage,
    Effort,
    ImageInput,
    ImageResult,
    T,
    Tier,
    Usage,
)
from app.ai.gemini_provider import GeminiProvider
from app.ai.offline_provider import OfflineProvider
from app.ai.openai_provider import OpenAIProvider
from app.ai.pricing import cost_usd
from app.core.config import get_settings
from app.core.logging import log

logger = logging.getLogger("ai")

# Same-tier defaults used as fallbacks when the configured provider is unavailable or failing.
PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "anthropic": {
        "planning": "claude-opus-5", "content": "claude-sonnet-5", "fast": "claude-haiku-4-5",
        "vision": "claude-sonnet-5", "qc": "claude-haiku-4-5",
    },
    "openai": {
        "planning": "gpt-5.5", "content": "gpt-5.4-mini", "fast": "gpt-5.4-nano", "vision": "gpt-5.4-mini",
        "qc": "gpt-5.4-nano", "embedding": "text-embedding-3-small", "image": "gpt-image-1-mini",
        "video": "sora-2",
    },
    "gemini": {
        "planning": "gemini-2.5-pro", "content": "gemini-3.5-flash", "fast": "gemini-3.1-flash-lite",
        "vision": "gemini-3.5-flash", "qc": "gemini-3.1-flash-lite", "embedding": "gemini-embedding-001",
        "image": "gemini-2.5-flash-image", "video": "veo-3.0-fast-generate-001",
    },
}
PROVIDER_ORDER = ["anthropic", "openai", "gemini"]


@dataclass
class Route:
    provider: str
    model: str


class _LRU:
    def __init__(self, size: int = 512):
        self.size = size
        self.data: OrderedDict[str, Any] = OrderedDict()

    def get(self, key: str) -> Any:
        if key in self.data:
            self.data.move_to_end(key)
            return self.data[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.data.move_to_end(key)
        while len(self.data) > self.size:
            self.data.popitem(last=False)


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
            "anthropic": AnthropicProvider(),
            "openai": OpenAIProvider(),
            "gemini": GeminiProvider(),
            "offline": OfflineProvider(),
        }
        self._sem = asyncio.Semaphore(self.settings.ai_max_concurrency)
        self._cache = _LRU()
        self._overrides: dict[str, Any] = {}
        self._overrides_at = 0.0
        self.breaker = CircuitBreaker()

    # ------------------------------------------------------------------ routing

    @property
    def live_providers(self) -> list[str]:
        if self.settings.ai_offline_mode:
            return []
        return [p for p in PROVIDER_ORDER if self.providers[p].available()]

    @property
    def mode(self) -> str:
        return "live" if self.live_providers else "offline"

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
        chain = healthy or chain  # if every provider is tripped, still try them rather than fail outright
        chain.append(Route("offline", "offline"))
        return chain

    # ------------------------------------------------------------------ accounting

    async def _record(self, *, task: str, route: Route, usage: Usage, latency_ms: int, success: bool,
                      owner_id: uuid.UUID | None, job_id: uuid.UUID | None, error: str | None = None,
                      prompt_version: str | None = None) -> float:
        overrides = await self._load_overrides()
        cost = cost_usd(route.model, usage, overrides.get("ai_pricing"))
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
            from app.models import AIUsage, GenerationJob, ProviderHealth

            async with get_sessionmaker()() as s:
                s.add(AIUsage(owner_id=owner_id, job_id=job_id, task=task, provider=route.provider,
                              model=route.model, prompt_version=prompt_version,
                              input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                              cached_tokens=usage.cached_tokens, images=usage.images, cost_usd=cost,
                              latency_ms=latency_ms, success=success, error=(error or "")[:2000] or None,
                              request_id=request_id_var.get(), error_code=_error_code(error) if error else None))
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

    async def structured(
        self,
        *,
        task: str,
        tier: Tier,
        system: str,
        prompt: str,
        schema: type[T],
        images: list[ImageInput] | None = None,
        effort: Effort = "medium",
        max_tokens: int = 16000,
        owner_id: uuid.UUID | None = None,
        job_id: uuid.UUID | None = None,
        offline_context: dict[str, Any] | None = None,
        prompt_version: str | None = None,
        cache: bool = False,
    ) -> T:
        base_req = AIRequest(task=task, system=system, messages=[ChatMessage("user", prompt, images or [])],
                             max_tokens=max_tokens, effort=effort, offline_context=offline_context or {})
        last_error: Exception | None = None
        for route in await self.routes(tier):
            key = self._cache_key(task, route.model, system, prompt, schema.__name__) if cache else None
            if key and (hit := self._cache.get(key)) is not None:
                return schema.model_validate(hit)
            req = base_req
            for attempt in range(2):
                start = time.monotonic()
                try:
                    async with self._sem:
                        result = await self.providers[route.provider].generate_structured(route.model, req, schema)
                    await self._record(task=task, route=route, usage=result.usage,
                                       latency_ms=int((time.monotonic() - start) * 1000), success=True,
                                       owner_id=owner_id, job_id=job_id, prompt_version=prompt_version)
                    if key:
                        self._cache.set(key, result.data.model_dump())
                    return result.data  # type: ignore[return-value]
                except AIRefusal:
                    raise
                except AIError as e:
                    last_error = e
                    await self._record(task=task, route=route, usage=Usage(), success=False,
                                       latency_ms=int((time.monotonic() - start) * 1000), owner_id=owner_id,
                                       job_id=job_id, error=str(e), prompt_version=prompt_version)
                    if not e.retryable:
                        break
                    if "validation" in str(e).lower():
                        # Feed the validation error back so the model can correct itself.
                        req = AIRequest(task=task, system=system, max_tokens=max_tokens, effort=effort,
                                        offline_context=base_req.offline_context, messages=[
                                            ChatMessage("user", prompt + "\n\nYour previous answer was invalid: "
                                                        + str(e)[:1500] + "\nReturn corrected JSON only.",
                                                        images or [])])
                    elif "truncated" in str(e).lower():
                        req = AIRequest(task=task, system=system, messages=req.messages, effort="low",
                                        max_tokens=min(max_tokens * 2, 64000),
                                        offline_context=base_req.offline_context)
                    else:
                        await asyncio.sleep(1.5 * (attempt + 1))
        raise AIError(f"All AI providers failed for task {task}: {last_error}", retryable=False)

    async def text(self, *, task: str, tier: Tier, system: str, messages: list[ChatMessage],
                   effort: Effort = "medium", max_tokens: int = 8000, owner_id: uuid.UUID | None = None,
                   job_id: uuid.UUID | None = None, offline_context: dict[str, Any] | None = None) -> str:
        req = AIRequest(task=task, system=system, messages=messages, max_tokens=max_tokens, effort=effort,
                        offline_context=offline_context or {})
        last_error: Exception | None = None
        for route in await self.routes(tier):
            start = time.monotonic()
            try:
                async with self._sem:
                    result = await self.providers[route.provider].generate_text(route.model, req)
                await self._record(task=task, route=route, usage=result.usage, success=True,
                                   latency_ms=int((time.monotonic() - start) * 1000), owner_id=owner_id,
                                   job_id=job_id)
                return result.text
            except AIRefusal:
                raise
            except AIError as e:
                last_error = e
                await self._record(task=task, route=route, usage=Usage(), success=False, error=str(e),
                                   latency_ms=int((time.monotonic() - start) * 1000), owner_id=owner_id,
                                   job_id=job_id)
        raise AIError(f"All AI providers failed for task {task}: {last_error}", retryable=False)

    async def stream(self, *, task: str, tier: Tier, system: str, messages: list[ChatMessage],
                     effort: Effort = "low", max_tokens: int = 4000, owner_id: uuid.UUID | None = None,
                     offline_context: dict[str, Any] | None = None) -> AsyncIterator[str]:
        req = AIRequest(task=task, system=system, messages=messages, max_tokens=max_tokens, effort=effort,
                        offline_context=offline_context or {})
        for route in await self.routes(tier):
            usage = Usage()
            start = time.monotonic()
            emitted = False
            try:
                async for chunk in self.providers[route.provider].stream_text(route.model, req, usage):
                    emitted = True
                    yield chunk
                await self._record(task=task, route=route, usage=usage, success=True,
                                   latency_ms=int((time.monotonic() - start) * 1000), owner_id=owner_id,
                                   job_id=None)
                return
            except AIError as e:
                await self._record(task=task, route=route, usage=usage, success=False, error=str(e),
                                   latency_ms=int((time.monotonic() - start) * 1000), owner_id=owner_id,
                                   job_id=None)
                if emitted:
                    yield "\n\n(Sorry — the answer was interrupted. Please try again.)"
                    return

    async def embed(self, texts: list[str], owner_id: uuid.UUID | None = None) -> list[list[float]]:
        if not texts:
            return []
        dim = self.settings.embedding_dim
        for route in await self.routes("embedding"):
            start = time.monotonic()
            try:
                vectors, usage = await self.providers[route.provider].generate_embedding(route.model, texts, dim)
                if route.provider != "offline":
                    await self._record(task="embedding", route=route, usage=usage, success=True,
                                       latency_ms=int((time.monotonic() - start) * 1000), owner_id=owner_id,
                                       job_id=None)
                return [list(v)[:dim] + [0.0] * max(0, dim - len(v)) for v in vectors]
            except AIError:
                continue
        raise AIError("Embedding failed", retryable=False)

    async def _media_routes(self, tier: Tier, model: str | None) -> list[Route]:
        """Routes for image/video, with an optional admin-chosen "provider:model" tried first."""
        chain = [r for r in await self.routes(tier) if r.provider != "offline"]
        if model and ":" in model:
            prov, name = model.split(":", 1)
            if prov in self.live_providers:
                chain = [Route(prov, name)] + [r for r in chain if (r.provider, r.model) != (prov, name)]
        return chain

    async def image(self, prompt: str, size: str = "1536x1024", owner_id: uuid.UUID | None = None,
                    job_id: uuid.UUID | None = None, model: str | None = None,
                    task: str = "image") -> ImageResult | None:
        """Generate an image. Returns None in offline mode (callers fall back to a placeholder)."""
        return await self._media(task, "image", model, owner_id, job_id,
                                 lambda p, m: p.generate_image(m, prompt, size))

    async def video(self, prompt: str, seconds: int = 4, aspect: str = "16:9", owner_id: uuid.UUID | None = None,
                    job_id: uuid.UUID | None = None, model: str | None = None) -> ImageResult | None:
        """Generate a short video clip. Returns None in offline mode."""
        return await self._media("video", "video", model, owner_id, job_id,
                                 lambda p, m: p.generate_video(m, prompt, seconds, aspect))

    async def _media(self, task: str, tier: Tier, model: str | None, owner_id: uuid.UUID | None,
                     job_id: uuid.UUID | None, call) -> ImageResult | None:
        routes = await self._media_routes(tier, model)
        if not routes:
            return None
        last: AIError | None = None
        for route in routes:
            start = time.monotonic()
            try:
                result = await call(self.providers[route.provider], route.model)
                await self._record(task=task, route=route, usage=result.usage, success=True,
                                   latency_ms=int((time.monotonic() - start) * 1000), owner_id=owner_id,
                                   job_id=job_id)
                return result
            except AIRefusal:
                raise
            except AIError as e:
                last = e
                await self._record(task=task, route=route, usage=Usage(), success=False, error=str(e),
                                   latency_ms=int((time.monotonic() - start) * 1000), owner_id=owner_id,
                                   job_id=job_id)
        raise last or AIError(f"{tier} generation failed", retryable=True)


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
