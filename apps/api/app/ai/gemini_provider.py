"""Google Gemini adapter using the `google-genai` SDK."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from pydantic import ValidationError

from app.ai.base import AIError, AIRequest, ImageResult, StructuredResult, T, TextResult, Usage
from app.ai.schema_utils import extract_json, strict_schema
from app.core.config import get_settings


class GeminiProvider:
    name = "gemini"

    def __init__(self) -> None:
        s = get_settings()
        self._client = None
        if s.gemini_api_key:
            from google import genai

            self._client = genai.Client(api_key=s.gemini_api_key)

    def available(self) -> bool:
        return self._client is not None

    def _contents(self, req: AIRequest) -> list[Any]:
        from google.genai import types

        contents = []
        for m in req.messages:
            parts = [types.Part.from_bytes(data=i.data, mime_type=i.media_type) for i in m.images]
            parts.append(types.Part.from_text(text=m.content))
            contents.append(types.Content(role="user" if m.role == "user" else "model", parts=parts))
        return contents

    def _config(self, req: AIRequest, json_schema: dict | None = None):
        from google.genai import types

        kwargs: dict[str, Any] = {"system_instruction": req.system, "max_output_tokens": req.max_tokens}
        if json_schema is not None:
            kwargs["response_mime_type"] = "application/json"
            kwargs["response_json_schema"] = json_schema
        return types.GenerateContentConfig(**kwargs)

    @staticmethod
    def _usage(resp: Any) -> Usage:
        u = getattr(resp, "usage_metadata", None)
        if not u:
            return Usage()
        cached = getattr(u, "cached_content_token_count", 0) or 0
        return Usage(
            input_tokens=(u.prompt_token_count or 0) - cached,
            output_tokens=(u.candidates_token_count or 0) + (getattr(u, "thoughts_token_count", 0) or 0),
            cached_tokens=cached,
        )

    async def _generate(self, model: str, req: AIRequest, json_schema: dict | None = None) -> Any:
        assert self._client is not None
        try:
            resp = await self._client.aio.models.generate_content(
                model=model, contents=self._contents(req), config=self._config(req, json_schema)
            )
        except Exception as e:  # google-genai raises google.genai.errors.APIError subclasses
            code = getattr(e, "code", 500) or 500
            raise AIError(f"Gemini error: {e}", retryable=code >= 429, provider=self.name) from e
        if not resp.candidates:
            raise AIError("Gemini returned no candidates (blocked)", retryable=False, provider=self.name)
        return resp

    async def generate_text(self, model: str, req: AIRequest) -> TextResult:
        resp = await self._generate(model, req)
        return TextResult(resp.text or "", self._usage(resp), model, self.name)

    async def stream_text(self, model: str, req: AIRequest, usage_out: Usage) -> AsyncIterator[str]:
        assert self._client is not None
        try:
            stream = await self._client.aio.models.generate_content_stream(
                model=model, contents=self._contents(req), config=self._config(req)
            )
            async for chunk in stream:
                if chunk.text:
                    yield chunk.text
                if getattr(chunk, "usage_metadata", None):
                    u = self._usage(chunk)
                    usage_out.input_tokens, usage_out.output_tokens = u.input_tokens, u.output_tokens
        except Exception as e:
            raise AIError(f"Gemini stream error: {e}", retryable=False, provider=self.name) from e

    async def generate_structured(self, model: str, req: AIRequest, schema: type[T]) -> StructuredResult:
        resp = await self._generate(model, req, json_schema=strict_schema(schema))
        try:
            data = schema.model_validate(extract_json(resp.text or ""))
        except (ValidationError, json.JSONDecodeError, ValueError) as e:
            raise AIError(f"Structured output failed validation: {e}", retryable=True, provider=self.name) from e
        return StructuredResult(data, self._usage(resp), model, self.name)

    async def generate_embedding(self, model: str, texts: list[str], dim: int):
        from google.genai import types

        assert self._client is not None
        try:
            resp = await self._client.aio.models.embed_content(
                model=model, contents=texts, config=types.EmbedContentConfig(output_dimensionality=dim)
            )
        except Exception as e:
            raise AIError(f"Gemini embedding error: {e}", retryable=True, provider=self.name) from e
        return [e.values for e in resp.embeddings], Usage(input_tokens=sum(len(t) // 4 for t in texts))

    async def generate_image(self, model: str, prompt: str, size: str) -> ImageResult:
        from google.genai import types

        assert self._client is not None
        aspect = {"1536x1024": "3:2", "1024x1536": "2:3"}.get(size, "1:1")
        try:
            # Image-capable Gemini models (e.g. gemini-2.5-flash-image) via generate_content.
            resp = await self._client.aio.models.generate_content(
                model=model,
                contents=f"{prompt}\n\nAspect ratio {aspect}.",
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
            )
        except Exception as e:
            raise AIError(f"Gemini image error: {e}", retryable=True, provider=self.name) from e
        for cand in resp.candidates or []:
            for part in (cand.content.parts if cand.content else []) or []:
                if part.inline_data and part.inline_data.data:
                    return ImageResult(part.inline_data.data, part.inline_data.mime_type or "image/png",
                                       Usage(images=1), model, self.name)
        raise AIError("Gemini returned no image", retryable=False, provider=self.name)
