"""Isolated adapter tests; no paid calls or database required (--noconftest)."""
import base64
import json
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import openai
import pytest
from PIL import Image
from pydantic import BaseModel

from app.ai.base import AIError, AIRequest
from app.ai.budget import RateCard
from app.ai.openrouter_provider import OPENROUTER_MODELS, OpenRouterProvider
from app.ai.service import AIService, CircuitBreaker


def adapter():
    return OpenRouterProvider.__new__(OpenRouterProvider)


@pytest.mark.asyncio
async def test_strict_json_through_sdk():
    captured = []

    def respond(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "test", "object": "chat.completion", "created": 0,
            "model": "anthropic/claude-sonnet-4.6", "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": '{"title":"Fractions"}'}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 20,
                      "prompt_tokens_details": {"cached_tokens": 30, "cache_write_tokens": 10}}})

    class Slide(BaseModel):
        title: str

    provider = adapter()
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider._client = openai.AsyncOpenAI(api_key="test", base_url="https://openrouter.ai/api/v1",
                                             http_client=client)
        result = await provider.generate_structured(OPENROUTER_MODELS["planning"],
                                                    AIRequest("slides", "Stable instructions", []), Slide)
    assert result.data.title == "Fractions"
    assert result.usage.input_tokens == 80
    assert result.usage.cache_write_tokens == 10
    body = captured[0]
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["provider"]["require_parameters"] is True
    assert body["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert body["reasoning"] == {"effort": "medium"}


@pytest.mark.asyncio
async def test_image_endpoint_and_validation():
    image = BytesIO()
    Image.new("RGB", (16, 16)).save(image, format="PNG")
    captured = []

    def respond(request):
        captured.append(request.url.path)
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(image.getvalue()).decode()}]})

    provider = adapter()
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider._client = openai.AsyncOpenAI(api_key="test", base_url="https://openrouter.ai/api/v1",
                                             http_client=client)
        result = await provider.generate_image(OPENROUTER_MODELS["image"], "Fraction diagram", "1536x1024")
    assert captured == ["/api/v1/images"]
    assert result.media_type == "image/png"
    assert result.usage.reported is False
    provider._client = SimpleNamespace(post=AsyncMock(return_value={"data": [{"b64_json": "invalid"}]}))
    with pytest.raises(AIError, match="invalid raster"):
        await provider.generate_image("image", "prompt", "1024x1024")


@pytest.mark.asyncio
async def test_router_only_and_separate_task_models():
    service = AIService.__new__(AIService)
    service.settings = SimpleNamespace(ai_offline_mode=False, openrouter_only=True,
        **{"model_" + k: "openrouter:" + v for k, v in OPENROUTER_MODELS.items()})
    service.providers = {name: SimpleNamespace(available=lambda: True)
                         for name in ("openrouter", "openai", "anthropic")}
    service._load_overrides = AsyncMock(return_value={})
    service.breaker = CircuitBreaker()
    assert service.live_providers == ["openrouter"]
    assert (await service.routes("planning"))[0].model == OPENROUTER_MODELS["planning"]
    assert (await service.routes("content"))[0].model == OPENROUTER_MODELS["content"]
    service.providers["openrouter"].available = lambda: False
    assert await service.routes("content") == []


def test_error_response_and_price_cards():
    with pytest.raises(AIError):
        adapter()._check(SimpleNamespace(choices=[], error={"code": 402}, usage=None))
    from pathlib import Path
    cards = json.loads((Path(__file__).resolve().parents[3] / "docs/openrouter-rate-cards.json").read_text())
    for model in OPENROUTER_MODELS.values():
        RateCard.model_validate(cards["openrouter:" + model])


@pytest.mark.asyncio
async def test_stream_error_is_not_silent_success():
    provider = adapter()

    class Stream:
        def __aiter__(self):
            return self.chunks()

        async def chunks(self):
            yield SimpleNamespace(error={"code": 500}, choices=[], usage=None)

        async def close(self):
            self.closed = True

    stream = Stream()
    provider._call = AsyncMock(return_value=stream)
    from app.ai.base import Usage
    with pytest.raises(AIError, match="stream failed"):
        async for _ in provider.stream_text("openai/gpt-5.4-mini", AIRequest("chat", "system", []), Usage()):
            pass
    assert stream.closed


@pytest.mark.asyncio
async def test_search_retains_non_token_spending_hold():
    provider = adapter()
    response = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=10, completion_tokens=10))
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=AsyncMock(return_value=response))))
    result = await provider._call(model="perplexity/sonar")
    assert provider._usage(result).reported is False
