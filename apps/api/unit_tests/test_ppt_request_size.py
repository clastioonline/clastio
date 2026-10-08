import io
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from app.ai.base import AIRequest, ChatMessage, ImageInput
from app.ai.budget import BudgetError, BudgetPolicy
from app.ai.request_size import fit_ppt_request


def test_large_references_fit_without_changing_original_images():
    output = io.BytesIO()
    Image.effect_noise((1800, 1200), 100).convert('RGB').save(output, 'PNG')
    original = ImageInput(output.getvalue())
    req = AIRequest(task='lesson_deck', system='', messages=[ChatMessage('user', 'brief', [original, original])], max_tokens=24000)
    fitted = fit_ppt_request(req, BudgetPolicy(max_output_tokens=16000), 40000)
    assert sum(len(image.data) for image in fitted.messages[0].images) + 40000 <= 120000
    assert len(fitted.messages[0].images) == 2
    assert fitted.max_tokens == 16000
    assert req.max_tokens == 24000
    assert req.messages[0].images[0] is original
    assert original.media_type == 'image/png'
    for image in fitted.messages[0].images:
        with Image.open(io.BytesIO(image.data)) as decoded:
            assert decoded.format == 'JPEG'
            assert min(decoded.size) >= 240


def test_small_images_are_preserved_and_outputs_never_increased():
    original = ImageInput(b'small')
    req = AIRequest(task='lesson_deck', system='', messages=[ChatMessage('user', '', [original])], max_tokens=6000)
    fitted = fit_ppt_request(req, BudgetPolicy(), 100)
    assert fitted.messages[0].images[0] is original
    assert fitted.max_tokens == 6000


def test_source_text_is_not_silently_removed():
    req = AIRequest(task='lesson_deck', system='', messages=[])
    with pytest.raises(BudgetError, match='teaching text needs'):
        fit_ppt_request(req, BudgetPolicy(), 120001)


async def test_structured_ppt_uses_fitted_request_for_admission_and_provider(monkeypatch):
    from types import SimpleNamespace

    from pydantic import BaseModel

    from app.ai import service

    class Reply(BaseModel):
        title: str

    ai = service.AIService()
    monkeypatch.setattr(service.AIService, 'mode', property(lambda self: 'live'))
    db = AsyncMock()
    monkeypatch.setattr(service, 'get_sessionmaker', lambda: lambda: db)
    monkeypatch.setattr(service.budget, 'config', AsyncMock(return_value=(BudgetPolicy(max_output_tokens=8000), {})))
    monkeypatch.setattr(ai, 'routes', AsyncMock(return_value=[service.Route('openrouter', 'test')]))
    provider = SimpleNamespace(generate_structured=AsyncMock(return_value=SimpleNamespace(data=Reply(title='Ready'))))
    ai.providers['openrouter'] = provider
    async def execute(**kwargs):
        assert kwargs['output_tokens'] == 8000
        return await kwargs['call']()
    monkeypatch.setattr(ai, '_execute', execute)
    reply = await ai.structured(task='lesson_deck', tier='content', system='', prompt='brief', schema=Reply, max_tokens=24000)
    assert reply.title == 'Ready'
    assert provider.generate_structured.call_args.args[1].max_tokens == 8000
