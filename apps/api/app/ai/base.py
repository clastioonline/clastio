"""Provider-neutral AI interface.

Every provider adapter implements `AIProvider`. The application talks only to `AIService`
(app/ai/service.py), which routes a *task tier* to a provider/model, records usage and cost,
and falls back to another provider when one fails.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel

Tier = Literal["planning", "content", "fast", "vision", "qc", "embedding", "image", "video"]
Effort = Literal["low", "medium", "high"]

T = TypeVar("T", bound=BaseModel)


class AIError(Exception):
    def __init__(self, message: str, *, retryable: bool = True, provider: str | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.provider = provider


class AIRefusal(AIError):
    def __init__(self, message: str, provider: str | None = None):
        super().__init__(message, retryable=False, provider=provider)


@dataclass
class ImageInput:
    data: bytes
    media_type: str = "image/png"


@dataclass
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str
    images: list[ImageInput] = field(default_factory=list)


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    images: int = 0
    video_seconds: int = 0


@dataclass
class AIRequest:
    task: str
    system: str
    messages: list[ChatMessage]
    max_tokens: int = 16000
    effort: Effort = "medium"
    # Context for the offline provider (topic, grade, ...). Never sent to remote providers.
    offline_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class TextResult:
    text: str
    usage: Usage
    model: str
    provider: str


@dataclass
class StructuredResult:
    data: BaseModel
    usage: Usage
    model: str
    provider: str


@dataclass
class ImageResult:
    data: bytes
    media_type: str
    usage: Usage
    model: str
    provider: str


class AIProvider(Protocol):
    name: str

    def available(self) -> bool: ...

    async def generate_text(self, model: str, req: AIRequest) -> TextResult: ...

    def stream_text(self, model: str, req: AIRequest): ...  # AsyncIterator[str]; final usage via callback

    async def generate_structured(self, model: str, req: AIRequest, schema: type[T]) -> StructuredResult: ...

    async def generate_embedding(self, model: str, texts: list[str], dim: int) -> tuple[list[list[float]], Usage]: ...

    async def generate_image(self, model: str, prompt: str, size: str) -> ImageResult: ...

    async def generate_video(self, model: str, prompt: str, seconds: int, aspect: str) -> ImageResult: ...
