"""OpenRouter task models, strict JSON, vision and normalized image generation."""

from __future__ import annotations

import base64
import binascii
from collections.abc import AsyncIterator
from io import BytesIO
from typing import Any

import openai
from PIL import Image, UnidentifiedImageError

from app.ai.base import AIError, AIRequest, ImageResult, Usage
from app.ai.openai_provider import OpenAIProvider
from app.core.config import get_settings

OPENROUTER_MODELS = {
    "planning": "anthropic/claude-sonnet-4.6",
    "content": "openai/gpt-5.4-mini",
    "fast": "google/gemini-3.5-flash-lite",
    "qc": "openai/gpt-5.4-mini",
    "vision": "google/gemini-3.5-flash",
    "ingestion": "google/gemini-3.5-flash",
    "reflection": "openai/gpt-5.4-mini",
    "search": "perplexity/sonar",
    "embedding": "openai/text-embedding-3-small",
    "image": "google/gemini-3.1-flash-image",
}


class OpenRouterProvider(OpenAIProvider):
    name = "openrouter"

    def __init__(self) -> None:
        settings = get_settings()
        self._client = (
            openai.AsyncOpenAI(
                api_key=settings.openrouter_api_key,
                base_url="https://openrouter.ai/api/v1",
                timeout=settings.ai_request_timeout_s,
                max_retries=0,
                default_headers={"HTTP-Referer": settings.public_web_url, "X-Title": settings.app_name},
            ) if settings.openrouter_api_key else None
        )

    def _params(self, model: str, req: AIRequest) -> dict[str, Any]:
        messages = self._messages(req)
        if model.startswith("anthropic/") and req.system:
            messages[0]["content"] = [{"type": "text", "text": req.system,
                                       "cache_control": {"type": "ephemeral"}}]
        extra: dict[str, Any] = {"provider": {"require_parameters": True}, "usage": {"include": True}}
        if model.startswith(("openai/gpt-5", "google/gemini-3", "anthropic/claude-sonnet-4")):
            extra["reasoning"] = {"effort": req.effort}
        return {"model": model, "messages": messages, "max_tokens": req.max_tokens, "extra_body": extra}

    @staticmethod
    def _usage(resp: Any) -> Usage:
        usage = OpenAIProvider._usage(resp)
        details = getattr(getattr(resp, "usage", None), "prompt_tokens_details", None)
        written = getattr(details, "cache_write_tokens", 0) or 0
        import math
        cost = getattr(getattr(resp, "usage", None), "cost", None)
        if isinstance(cost, (int, float)) and math.isfinite(cost) and cost >= 0:
            usage.reported_cost_usd = float(cost)
            usage.reported = True
        usage.cache_write_tokens = written
        usage.input_tokens = max(0, usage.input_tokens - written)
        return usage

    def _check(self, resp: Any) -> str:
        if getattr(resp, "error", None) or not getattr(resp, "choices", None):
            raise AIError("OpenRouter returned an error or no completion", retryable=False,
                          provider=self.name, usage=self._usage(resp))
        if resp.choices[0].finish_reason in ("error", "content_filter"):
            raise AIError("OpenRouter could not complete this request", retryable=False,
                          provider=self.name, usage=self._usage(resp))
        return super()._check(resp)

    async def _call(self, **params: Any) -> Any:
        response = await super()._call(**params)
        # Search can carry request fees that cannot be priced from token counts.
        if not params.get("stream") and str(params.get("model", "")).startswith("perplexity/"):
            if self._usage(response).reported_cost_usd is None:
                response.usage = None
        return response

    async def generate_text(self, model: str, req: AIRequest):
        from urllib.parse import urlsplit

        from app.ai.base import TextResult

        response = await self._call(**self._params(model, req))
        answer = self._check(response)
        if model.startswith("perplexity/"):
            links = [url for url in (getattr(response, "citations", None) or [])
                     if isinstance(url, str) and urlsplit(url).scheme == "https"]
            if links:
                answer += "\n\nSources:\n" + "\n".join(links[:10])
        return TextResult(answer, self._usage(response), model, self.name)

    async def stream_text(self, model: str, req: AIRequest, usage_out: Usage) -> AsyncIterator[str]:
        stream = await self._call(**(self._params(model, req) | {
            "stream": True, "stream_options": {"include_usage": True},
        }))
        finished = False
        try:
            async for chunk in stream:
                if getattr(chunk, "error", None):
                    raise AIError("OpenRouter stream failed", retryable=False, provider=self.name)
                if getattr(chunk, "usage", None) and not model.startswith("perplexity/"):
                    usage_out.__dict__.update(self._usage(chunk).__dict__)
                for choice in chunk.choices:
                    reason = choice.finish_reason
                    if reason in ("length", "error", "content_filter") or getattr(choice.delta, "refusal", None):
                        raise AIError("OpenRouter stream was interrupted or declined", retryable=False,
                                      provider=self.name, usage=usage_out)
                    finished = finished or reason == "stop"
                    if choice.delta.content:
                        yield choice.delta.content
            if not finished:
                raise AIError("OpenRouter stream ended without completion", retryable=False, provider=self.name)
        except openai.APIError as exc:
            raise AIError("OpenRouter stream connection failed", retryable=False, provider=self.name) from exc
        finally:
            await stream.close()

    async def generate_image(self, model: str, prompt: str, size: str) -> ImageResult:
        assert self._client is not None
        try:
            response = await self._client.post("/images", cast_to=dict,
                                               body={"model": model, "prompt": prompt, "size": size})
        except openai.APIError as exc:
            raise AIError("OpenRouter image request failed", retryable=False, provider=self.name) from exc
        try:
            encoded = response["data"][0]["b64_json"]
            if not isinstance(encoded, str) or len(encoded) > 28_000_000:
                raise ValueError("Image exceeds size limit")
            data = base64.b64decode(encoded, validate=True)
            with Image.open(BytesIO(data)) as image:
                media_type = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[image.format]
                image.verify()
        except (KeyError, IndexError, TypeError, ValueError, binascii.Error,
                UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise AIError("OpenRouter returned an invalid raster image", retryable=False,
                          provider=self.name, usage=Usage(reported=False)) from exc
        # Keep the approved spending ceiling until variable image charges are reconciled.
        return ImageResult(data, media_type, Usage(images=1, reported=False), model, self.name)

    async def generate_video(self, model: str, prompt: str, seconds: int, aspect: str) -> ImageResult:
        raise AIError("OpenRouter video generation is not supported by this adapter", retryable=False,
                      provider=self.name)
