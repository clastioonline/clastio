"""Turn Pydantic models into the strict JSON Schema subset that providers' structured outputs accept.

- inline all $refs (no $defs)
- every object: additionalProperties=false and all properties required
- drop keywords providers commonly reject (title, default, min/max constraints, formats)
Pydantic still validates the full model (including constraints) after the response arrives.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from pydantic import BaseModel

_DROP = {
    "title", "default", "examples", "minLength", "maxLength", "minimum", "maximum",
    "exclusiveMinimum", "exclusiveMaximum", "minItems", "maxItems", "pattern", "format",
    "uniqueItems", "multipleOf", "discriminator", "minProperties", "maxProperties", "patternProperties",
}


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].split("/")[-1]
                target = copy.deepcopy(defs[name])
                extra = {k: v for k, v in node.items() if k != "$ref"}
                target.update(extra)
                return resolve(target)
            out = {
                k: ({name: resolve(prop) for name, prop in v.items()} if k == "properties" else resolve(v))
                for k, v in node.items() if k not in _DROP
            }
            if out.get("type") == "object" or "properties" in out:
                props = out.get("properties", {})
                out["type"] = "object"
                out["properties"] = props
                out["additionalProperties"] = False
                out["required"] = list(props.keys())
            return out
        if isinstance(node, list):
            return [resolve(x) for x in node]
        return node

    return resolve(raw)


def schema_hint(model: type[BaseModel]) -> str:
    """Compact schema text for providers without native structured output (and for the offline provider)."""
    return json.dumps(strict_schema(model), separators=(",", ":"))


def extract_json(text: str) -> Any:
    """Parse JSON from a model response, tolerating code fences or leading prose."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        start = min((i for i in (t.find("{"), t.find("[")) if i >= 0), default=-1)
        if start < 0:
            raise
        end = max(t.rfind("}"), t.rfind("]"))
        return json.loads(t[start : end + 1])
