"""Deterministic offline provider.

Used for automated tests, local development without API keys, and demo mode. It never calls the
network. Task-specific generators (registered from app/generation/offline.py) produce
schema-valid, curriculum-shaped content so the full pipeline - planning, rendering, QC and
exports - can be exercised end to end. Output quality is intentionally plain; connect a real
provider for production content.
"""

from __future__ import annotations

import hashlib
import math
import re
import types
import typing
from collections.abc import AsyncIterator, Callable
from typing import Any, Literal, get_args, get_origin

from pydantic import BaseModel

from app.ai.base import AIError, AIRequest, ImageResult, StructuredResult, T, TextResult, Usage

OfflineStructuredFn = Callable[[dict[str, Any], type[BaseModel]], BaseModel]
OfflineTextFn = Callable[[dict[str, Any], AIRequest], str]

STRUCTURED_GENERATORS: dict[str, OfflineStructuredFn] = {}
TEXT_GENERATORS: dict[str, OfflineTextFn] = {}


def register_structured(task: str):
    def deco(fn: OfflineStructuredFn) -> OfflineStructuredFn:
        STRUCTURED_GENERATORS[task] = fn
        return fn

    return deco


def register_text(task: str):
    def deco(fn: OfflineTextFn) -> OfflineTextFn:
        TEXT_GENERATORS[task] = fn
        return fn

    return deco


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def fill_schema(schema: type[BaseModel], hint: str = "Item") -> BaseModel:
    """Build a minimal valid instance of any Pydantic model (generic fallback)."""

    def value_for(annotation: Any, name: str) -> Any:
        origin = get_origin(annotation)
        args = get_args(annotation)
        if origin in (typing.Union, types.UnionType):
            non_none = [a for a in args if a is not type(None)]
            return value_for(non_none[0], name) if non_none else None
        if origin is Literal:
            return args[0]
        if origin in (list, typing.List):  # noqa: UP006
            return [value_for(args[0], name) for _ in range(2)] if args else []
        if origin is dict:
            return {}
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return build(annotation)
        if annotation is bool:
            return False
        if annotation is int:
            return 1
        if annotation is float:
            return 1.0
        return f"{hint} {name.replace('_', ' ')}"

    def build(model: type[BaseModel]) -> BaseModel:
        data = {n: value_for(f.annotation, n) for n, f in model.model_fields.items()}
        return model.model_validate(data)

    return build(schema)


class OfflineProvider:
    name = "offline"

    def available(self) -> bool:
        return True

    async def generate_text(self, model: str, req: AIRequest) -> TextResult:
        fn = TEXT_GENERATORS.get(req.task)
        text = fn(req.offline_context, req) if fn else (
            "I'm running in offline demo mode, so I can't write a free-form answer yet. "
            "Connect an AI provider key (Anthropic, OpenAI or Gemini) to enable full responses."
        )
        prompt = req.system + " ".join(m.content for m in req.messages)
        return TextResult(text, Usage(_estimate_tokens(prompt), _estimate_tokens(text)), "offline", self.name)

    async def stream_text(self, model: str, req: AIRequest, usage_out: Usage) -> AsyncIterator[str]:
        result = await self.generate_text(model, req)
        for word in re.split(r"(\s+)", result.text):
            if word:
                yield word
        usage_out.input_tokens, usage_out.output_tokens = result.usage.input_tokens, result.usage.output_tokens

    async def generate_structured(self, model: str, req: AIRequest, schema: type[T]) -> StructuredResult:
        fn = STRUCTURED_GENERATORS.get(req.task)
        data = fn(req.offline_context, schema) if fn else fill_schema(schema, req.offline_context.get("topic", "Item"))
        if not isinstance(data, schema):
            data = schema.model_validate(data.model_dump() if isinstance(data, BaseModel) else data)
        prompt = req.system + " ".join(m.content for m in req.messages)
        usage = Usage(_estimate_tokens(prompt), _estimate_tokens(data.model_dump_json()))
        return StructuredResult(data, usage, "offline", self.name)

    async def generate_embedding(self, model: str, texts: list[str], dim: int):
        return [hash_embedding(t, dim) for t in texts], Usage(input_tokens=sum(_estimate_tokens(t) for t in texts))

    async def generate_image(self, model: str, prompt: str, size: str) -> ImageResult:
        raise AIError("Offline mode does not generate images", retryable=False, provider=self.name)


_WORD = re.compile(r"[a-z0-9؀-ۿ]+")


def hash_embedding(text: str, dim: int) -> list[float]:
    """Feature-hashed bag of unigrams + bigrams, L2 normalised. Lexical similarity only."""
    vec = [0.0] * dim
    words = _WORD.findall(text.lower())
    grams = words + [f"{a}_{b}" for a, b in zip(words, words[1:], strict=False)]
    for g in grams:
        h = int.from_bytes(hashlib.blake2b(g.encode(), digest_size=8).digest(), "big")
        vec[h % dim] += 1.0 if (h >> 63) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]
