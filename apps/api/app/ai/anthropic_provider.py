"""Anthropic (Claude) adapter using the official `anthropic` SDK."""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from typing import Any

import anthropic
from pydantic import ValidationError

from app.ai.base import AIError, AIRefusal, AIRequest, ImageResult, StructuredResult, T, TextResult, Usage
from app.ai.schema_utils import extract_json, strict_schema
from app.core.config import get_settings

# Models that accept `output_config.effort` (Haiku 4.5 rejects it).
_EFFORT_PREFIXES = ("claude-opus-5", "claude-sonnet-5", "claude-fable", "claude-opus-4-8", "claude-opus-4-7",
                    "claude-opus-4-6", "claude-sonnet-4-6")
# Models where we opt into server-side refusal fallbacks.
_FALLBACK_PREFIXES = ("claude-opus-5", "claude-fable-5-1")


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        s = get_settings()
        self._client = (
            anthropic.AsyncAnthropic(api_key=s.anthropic_api_key, timeout=s.ai_request_timeout_s, max_retries=2)
            if s.anthropic_api_key
            else None
        )

    def available(self) -> bool:
        return self._client is not None

    # ------------------------------------------------------------------ helpers

    def _messages(self, req: AIRequest) -> list[dict[str, Any]]:
        out = []
        for m in req.messages:
            if m.images:
                blocks: list[dict[str, Any]] = [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": img.media_type,
                            "data": base64.standard_b64encode(img.data).decode(),
                        },
                    }
                    for img in m.images
                ]
                blocks.append({"type": "text", "text": m.content})
                out.append({"role": m.role, "content": blocks})
            else:
                out.append({"role": m.role, "content": m.content})
        return out

    def _params(self, model: str, req: AIRequest, output_format: dict | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": model,
            "max_tokens": req.max_tokens,
            # Stable per-task system prompt first, marked cacheable (prefix caching).
            "system": [{"type": "text", "text": req.system, "cache_control": {"type": "ephemeral"}}],
            "messages": self._messages(req),
        }
        output_config: dict[str, Any] = {}
        if model.startswith(_EFFORT_PREFIXES):
            output_config["effort"] = req.effort
        if output_format:
            output_config["format"] = output_format
        if output_config:
            params["output_config"] = output_config
        if model.startswith(_FALLBACK_PREFIXES):
            params["extra_headers"] = {"anthropic-beta": "server-side-fallback-2026-07-01"}
            params["extra_body"] = {"fallbacks": "default"}
        return params

    @staticmethod
    def _usage(msg: Any) -> Usage:
        u = msg.usage
        return Usage(
            input_tokens=(u.input_tokens or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0),
            output_tokens=u.output_tokens or 0,
            cached_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
        )

    @staticmethod
    def _text(msg: Any) -> str:
        return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")

    def _check_stop(self, msg: Any) -> None:
        if msg.stop_reason == "refusal":
            details = getattr(msg, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise AIRefusal(f"Request declined by model safety system (category={category})", provider=self.name)
        if msg.stop_reason == "max_tokens":
            raise AIError("Response truncated at max_tokens", retryable=True, provider=self.name)

    async def _call(self, params: dict[str, Any]) -> Any:
        assert self._client is not None
        try:
            # Stream to avoid HTTP timeouts on long outputs; collect the final message.
            async with self._client.messages.stream(**params) as stream:
                return await stream.get_final_message()
        except anthropic.BadRequestError as e:
            raise AIError(f"Anthropic bad request: {e.message}", retryable=False, provider=self.name) from e
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            raise AIError(f"Anthropic auth error: {e.message}", retryable=False, provider=self.name) from e
        except anthropic.NotFoundError as e:
            raise AIError(f"Anthropic model not found: {e.message}", retryable=False, provider=self.name) from e
        except anthropic.RateLimitError as e:
            raise AIError("Anthropic rate limited", retryable=True, provider=self.name) from e
        except anthropic.APIStatusError as e:
            raise AIError(f"Anthropic API error {e.status_code}", retryable=e.status_code >= 500,
                          provider=self.name) from e
        except anthropic.APIConnectionError as e:
            raise AIError("Anthropic connection error", retryable=True, provider=self.name) from e

    # ------------------------------------------------------------------ interface

    async def generate_text(self, model: str, req: AIRequest) -> TextResult:
        msg = await self._call(self._params(model, req))
        self._check_stop(msg)
        return TextResult(self._text(msg), self._usage(msg), model, self.name)

    async def stream_text(self, model: str, req: AIRequest, usage_out: Usage) -> AsyncIterator[str]:
        assert self._client is not None
        params = self._params(model, req)
        try:
            async with self._client.messages.stream(**params) as stream:
                async for text in stream.text_stream:
                    yield text
                final = await stream.get_final_message()
        except anthropic.APIError as e:
            raise AIError(f"Anthropic stream error: {e}", retryable=False, provider=self.name) from e
        u = self._usage(final)
        usage_out.input_tokens, usage_out.output_tokens, usage_out.cached_tokens = (
            u.input_tokens, u.output_tokens, u.cached_tokens)

    async def generate_structured(self, model: str, req: AIRequest, schema: type[T]) -> StructuredResult:
        fmt = {"type": "json_schema", "schema": strict_schema(schema)}
        msg = await self._call(self._params(model, req, output_format=fmt))
        self._check_stop(msg)
        text = self._text(msg)
        try:
            data = schema.model_validate(extract_json(text))
        except (ValidationError, json.JSONDecodeError, ValueError) as e:
            raise AIError(f"Structured output failed validation: {e}", retryable=True, provider=self.name) from e
        return StructuredResult(data, self._usage(msg), model, self.name)

    async def generate_embedding(self, model: str, texts: list[str], dim: int):
        raise AIError("Anthropic does not provide an embeddings endpoint", retryable=False, provider=self.name)

    async def generate_video(self, model: str, prompt: str, seconds: int, aspect: str) -> ImageResult:
        raise AIError("Anthropic does not provide video generation", retryable=False, provider=self.name)

    async def generate_image(self, model: str, prompt: str, size: str) -> ImageResult:
        raise AIError("Anthropic does not provide image generation", retryable=False, provider=self.name)
