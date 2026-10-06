"""Additional providers using their official OpenAI-compatible endpoints."""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import openai
from pydantic import ValidationError

from app.ai.base import AIError, AIRequest, StructuredResult, T, TextResult, Usage
from app.ai.openai_provider import OpenAIProvider
from app.ai.schema_utils import extract_json, strict_schema
from app.core.config import get_settings


class CompatibleProvider(OpenAIProvider):
    def __init__(self, name: str, key: str | None, url: str) -> None:
        self.name = name
        self._client = openai.AsyncOpenAI(api_key=key, base_url=url,
            timeout=get_settings().ai_request_timeout_s, max_retries=0) if key else None

    def _params(self, model: str, req: AIRequest) -> dict[str, Any]:
        params = super()._params(model, req)
        params["max_tokens"] = params.pop("max_completion_tokens")
        return params


    def _usage(self, response: Any) -> Usage:
        usage = super()._usage(response)
        if self.name == "perplexity":
            # Search/request charges are additional to tokens; preserve the approved ceiling.
            usage.reported = False
        return usage

    async def generate_text(self, model: str, req: AIRequest) -> TextResult:
        response = await self._call(**self._params(model, req))
        answer = self._check(response)
        if self.name == "perplexity":
            citations = getattr(response, "citations", None) or []
            safe = [url for url in citations if isinstance(url, str) and urlparse(url).scheme == "https"]
            if safe:
                answer += "\n\nSources:\n" + "\n".join(f"[{i}]({url})" for i, url in enumerate(safe[:10], 1))
        return TextResult(answer, self._usage(response), model, self.name)

    async def generate_structured(self, model: str, req: AIRequest, schema: type[T]) -> StructuredResult:
        params = self._params(model, req)
        if self.name == "groq":
            # Llama 3.3 supports JSON mode rather than strict JSON Schema mode.
            params["response_format"] = {"type": "json_object"}
            params["messages"][0]["content"] += "\nReturn JSON matching this schema: " + json.dumps(strict_schema(schema))
        else:
            params["response_format"] = {"type": "json_schema", "json_schema": {"schema": strict_schema(schema)}}
        response = await self._call(**params)
        try:
            data = schema.model_validate(extract_json(self._check(response)))
        except (ValidationError, ValueError) as exc:
            raise AIError("Structured output failed validation", provider=self.name, usage=self._usage(response)) from exc
        return StructuredResult(data, self._usage(response), model, self.name)
