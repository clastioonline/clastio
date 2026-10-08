"""Settings validation accepts the shipped OpenRouter profile without paid calls or a DB."""
import json
from pathlib import Path

import pytest

from app.api.routes.platform import _validate_setting
from app.core.errors import AppError

CARD = {'input': 1, 'output': 2, 'cached': .1, 'cache_write': 0,
        'ceiling_usd': .5, 'source': 'https://openrouter.ai/api/v1/models'}


def test_exact_openrouter_price_card_can_be_saved():
    path = Path(__file__).resolve().parents[3] / 'docs/openrouter-rate-cards.json'
    _validate_setting('ai_rate_cards', json.loads(path.read_text()))


@pytest.mark.parametrize('key', ['openai:gpt-5.4-mini', 'anthropic:claude-sonnet-4-6',
    'gemini:gemini-3.5-flash', 'groq:llama-3.3-70b-versatile', 'perplexity:sonar',
    'openrouter:anthropic/claude-sonnet-4.6', 'openrouter:meta-llama/llama-3.3-70b-instruct:free'])
def test_supported_provider_model_formats(key):
    _validate_setting('ai_rate_cards', {key: CARD})


@pytest.mark.parametrize('key', ['unknown:model', 'openrouter:', 'openrouter', 'openrouter: model', 'openrouter:model name'])
def test_invalid_provider_model_keys_stay_blocked(key):
    with pytest.raises(AppError):
        _validate_setting('ai_rate_cards', {key: CARD})


def test_invalid_rates_stay_blocked():
    with pytest.raises(AppError):
        _validate_setting('ai_rate_cards', {'openrouter:openai/gpt-5.4-mini': {**CARD, 'input': -1}})
