"""USD prices per 1M tokens (input, output, cached-input) and per image.

Anthropic prices are first-party list prices. Other providers' prices are placeholders to be
confirmed against their pricing pages; admins can override any entry at runtime via the
`ai_pricing` app setting, so cost dashboards stay accurate without a deploy.
"""

from __future__ import annotations

from app.ai.base import Usage

# model -> (input, output, cached_input)
TOKEN_PRICES: dict[str, tuple[float, float, float]] = {
    "claude-fable-5-1": (10.0, 50.0, 0.25),
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-opus-5": (5.0, 25.0, 0.50),
    "claude-sonnet-5": (2.0, 10.0, 0.20),
    "claude-haiku-4-5": (1.0, 5.0, 0.10),
    # --- estimates: verify on provider pricing pages ---
    "gpt-5.5": (1.25, 10.0, 0.125),
    "gpt-5.4-mini": (0.25, 2.0, 0.025),
    "gpt-5.4-nano": (0.05, 0.4, 0.005),
    "text-embedding-3-small": (0.02, 0.0, 0.0),
    "gemini-2.5-pro": (1.25, 10.0, 0.31),
    "gemini-3.5-flash": (0.30, 2.5, 0.075),
    "gemini-3.1-flash-lite": (0.10, 0.40, 0.025),
    "gemini-embedding-001": (0.15, 0.0, 0.0),
}

IMAGE_PRICES: dict[str, float] = {
    "gpt-image-1-mini": 0.011,
    "gpt-image-1": 0.042,
    "imagen-4.0-generate-001": 0.04,
}

DEFAULT_PRICE = (1.0, 5.0, 0.1)


def cost_usd(model: str, usage: Usage, overrides: dict | None = None) -> float:
    prices = dict(TOKEN_PRICES)
    img_prices = dict(IMAGE_PRICES)
    if overrides:
        prices.update({k: tuple(v) for k, v in overrides.get("tokens", {}).items()})
        img_prices.update(overrides.get("images", {}))
    if model.startswith("offline"):
        return 0.0
    inp, out, cached = prices.get(model, DEFAULT_PRICE)
    total = (usage.input_tokens * inp + usage.output_tokens * out + usage.cached_tokens * cached) / 1_000_000
    total += usage.images * img_prices.get(model, 0.04)
    return round(total, 6)
