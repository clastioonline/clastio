"""Selected Presenton helpers. Apache-2.0; see LICENSE.presenton.
Upstream commit 7376573fb30e4faf6225ff77d2cc74d06634b2e0.
Extracted from templates/v2/content.py; unused imports and hydration code omitted.
"""
import copy
import re
from typing import Any

_MARKDOWN_INLINE_PATTERNS = (
    re.compile(r"!\[([^\]]*)\]\([^)]*\)"),
    re.compile(r"\[([^\]]+)\]\([^)]*\)"),
    re.compile(r"`([^`]+)`"),
    re.compile(r"~~([^~]+)~~"),
    re.compile(r"\*\*\*([^*]+)\*\*\*"),
    re.compile(r"___([^_]+)___"),
    re.compile(r"\*\*([^*]+)\*\*"),
    re.compile(r"__([^_]+)__"),
    re.compile(r"\*([^*]+)\*"),
    re.compile(r"(?<!\w)_([^_]+)_(?!\w)"),
)


def infographic_markdown_to_plain_text(value: Any) -> Any:
    """Remove inline Markdown from generated infographic labels recursively."""
    if isinstance(value, str):
        for pattern in _MARKDOWN_INLINE_PATTERNS:
            value = pattern.sub(r"\1", value)
        return value
    if isinstance(value, list):
        return [infographic_markdown_to_plain_text(item) for item in value]
    if isinstance(value, dict):
        return {
            key: infographic_markdown_to_plain_text(item)
            for key, item in value.items()
        }
    return copy.deepcopy(value)


def repeated_child_source_index(
    index: int,
    *,
    template_count: int,
    content_count: int,
    center_when_reduced: bool,
) -> int:
    """Return the template child used for a repeated content item."""
    if center_when_reduced and content_count < template_count:
        start = (template_count - content_count) // 2
        return start + index
    return min(index, template_count - 1)

