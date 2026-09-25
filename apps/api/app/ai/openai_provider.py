"""OpenAI adapter. Also serves any OpenAI-compatible endpoint via OPENAI_BASE_URL."""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from typing import Any

import openai
from pydantic import ValidationError

from app.ai.base import AIError, AIRefusal, AIRequest, ImageResult, StructuredResult, T, TextResult, Usage
from app.ai.schema_utils import extract_json, strict_schema
from app.core.config import get_settings

_REASONING_PREFIXES = ("gpt-5", "gpt-6", "o1", "o3", "o4")


class OpenAIProvider:
    name = "openai"

    def __init__(self) -> None:
        s = get_settings()
        self._client = (
            openai.AsyncOpenAI(api_key=s.openai_api_key, base_url=s.openai_base_url,
                               timeout=s.ai_request_timeout_s, max_retries=2)
            if s.openai_api_key
            else None
        )

    def available(self) -> bool:
        return self._client is not None

    def _messages(self, req: AIRequest) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = [{"role": "system", "content": req.system}]
        for m in req.messages:
            if m.images:
                parts: list[dict[str, Any]] = [
                    {"type": "image_url",
                     "image_url": {"url": f"data:{i.media_type};base64,{base64.b64encode(i.data).decode()}"}}
                    for i in m.images
                ]
                parts.append({"type": "text", "text": m.content})
                out.append({"role": m.role, "content": parts})
            else:
                out.append({"role": m.role, "content": m.content})
        return out

    def _params(self, model: str, req: AIRequest) -> dict[str, Any]:
        p: dict[str, Any] = {"model": model, "messages": self._messages(req), "max_completion_tokens": req.max_tokens}
        if model.startswith(_REASONING_PREFIXES):
            p["reasoning_effort"] = req.effort
        return p

    @staticmethod
    def _usage(resp: Any) -> Usage:
        u = getattr(resp, "usage", None)
        if not u:
            return Usage()
        cached = 0
        details = getattr(u, "prompt_tokens_details", None)
        if details is not None:
            cached = getattr(details, "cached_tokens", 0) or 0
        return Usage(input_tokens=(u.prompt_tokens or 0) - cached, output_tokens=u.completion_tokens or 0,
                     cached_tokens=cached)

    async def _call(self, **params: Any) -> Any:
        assert self._client is not None
        try:
            return await self._client.chat.completions.create(**params)
        except openai.BadRequestError as e:
            raise AIError(f"OpenAI bad request: {e.message}", retryable=False, provider=self.name) from e
        except (openai.AuthenticationError, openai.PermissionDeniedError, openai.NotFoundError) as e:
            raise AIError(f"OpenAI error: {e.message}", retryable=False, provider=self.name) from e
        except openai.RateLimitError as e:
            raise AIError("OpenAI rate limited", retryable=True, provider=self.name) from e
        except openai.APIStatusError as e:
            raise AIError(f"OpenAI API error {e.status_code}", retryable=e.status_code >= 500,
                          provider=self.name) from e
        except openai.APIConnectionError as e:
            raise AIError("OpenAI connection error", retryable=True, provider=self.name) from e

    def _check(self, resp: Any) -> str:
        choice = resp.choices[0]
        if getattr(choice.message, "refusal", None):
            raise AIRefusal(choice.message.refusal, provider=self.name)
        if choice.finish_reason == "length":
            raise AIError("Response truncated", retryable=True, provider=self.name)
        return choice.message.content or ""

    async def generate_text(self, model: str, req: AIRequest) -> TextResult:
        resp = await self._call(**self._params(model, req))
        return TextResult(self._check(resp), self._usage(resp), model, self.name)

    async def stream_text(self, model: str, req: AIRequest, usage_out: Usage) -> AsyncIterator[str]:
        assert self._client is not None
        params = self._params(model, req) | {"stream": True, "stream_options": {"include_usage": True}}
        try:
            stream = await self._client.chat.completions.create(**params)
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                if getattr(chunk, "usage", None):
                    u = self._usage(chunk)
                    usage_out.input_tokens, usage_out.output_tokens, usage_out.cached_tokens = (
                        u.input_tokens, u.output_tokens, u.cached_tokens)
        except openai.APIError as e:
            raise AIError(f"OpenAI stream error: {e}", retryable=False, provider=self.name) from e

    async def generate_structured(self, model: str, req: AIRequest, schema: type[T]) -> StructuredResult:
        params = self._params(model, req)
        params["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": schema.__name__, "schema": strict_schema(schema), "strict": True},
        }
        resp = await self._call(**params)
        text = self._check(resp)
        try:
            data = schema.model_validate(extract_json(text))
        except (ValidationError, json.JSONDecodeError, ValueError) as e:
            raise AIError(f"Structured output failed validation: {e}", retryable=True, provider=self.name) from e
        return StructuredResult(data, self._usage(resp), model, self.name)

    async def generate_embedding(self, model: str, texts: list[str], dim: int):
        assert self._client is not None
        try:
            resp = await self._client.embeddings.create(model=model, input=texts, dimensions=dim)
        except openai.APIError as e:
            raise AIError(f"OpenAI embedding error: {e}", retryable=True, provider=self.name) from e
        vectors = [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]
        return vectors, Usage(input_tokens=resp.usage.prompt_tokens if resp.usage else 0)

    async def generate_image(self, model: str, prompt: str, size: str) -> ImageResult:
        assert self._client is not None
        try:
            resp = await self._client.images.generate(model=model, prompt=prompt, size=size, n=1,
                                                      quality="medium", output_format="png")
        except openai.APIError as e:
            raise AIError(f"OpenAI image error: {e}", retryable=True, provider=self.name) from e
        item = resp.data[0]
        if item.b64_json:
            data = base64.b64decode(item.b64_json)
        else:  # pragma: no cover - url responses (older models)
            import httpx

            async with httpx.AsyncClient() as client:
                data = (await client.get(item.url)).content
        return ImageResult(data, "image/png", Usage(images=1), model, self.name)

    async def generate_video(self, model: str, prompt: str, seconds: int, aspect: str) -> ImageResult:
        """Sora 2 via the Videos API: create, poll until done, download the MP4."""
        assert self._client is not None
        size = "720x1280" if aspect == "9:16" else "1280x720"
        seconds = min((4, 8, 12), key=lambda s: abs(s - seconds))
        try:
            video = await self._client.videos.create_and_poll(model=model, prompt=prompt, seconds=str(seconds),
                                                              size=size)
        except openai.APIError as e:
            raise AIError(f"OpenAI video error: {e}", retryable=True, provider=self.name) from e
        if video.status != "completed":
            err = video.error
            code = getattr(err, "code", "") or ""
            msg = getattr(err, "message", "") or str(err or video.status)
            if "moderation" in code or "policy" in code:
                raise AIRefusal(msg, provider=self.name)
            raise AIError(f"OpenAI video {video.status}: {msg}", retryable=False, provider=self.name)
        try:
            content = await self._client.videos.download_content(video.id, variant="video")
        except openai.APIError as e:
            raise AIError(f"OpenAI video download error: {e}", retryable=True, provider=self.name) from e
        return ImageResult(content.content, "video/mp4", Usage(video_seconds=seconds), model, self.name)
