"""Deterministic, schema-driven provider used for local development and tests.

FakeProvider has no domain knowledge: it never inspects ``model_purpose``
for meaning and never parses message content for task-specific control
strings. Given only ``output_json_schema`` and the message text, it derives
a deterministic, schema-conformant value for each declared property. This
keeps it reusable for any future use case without modification.

It never calls any real AI service and requires no credentials.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.providers.base import (
    GenerationMessage,
    StructuredGenerationRequest,
    StructuredGenerationResult,
    StructuredGenerationProvider,
)


class FakeProvider(StructuredGenerationProvider):
    async def generate(self, request: StructuredGenerationRequest) -> StructuredGenerationResult:
        text = _user_text(request.messages)
        seed = _stable_seed(request.model_purpose, text)
        properties: dict[str, Any] = request.output_json_schema.get("properties", {})

        data = {
            name: _fake_value(name, prop_schema, text, seed)
            for name, prop_schema in properties.items()
        }
        return StructuredGenerationResult(data=data)


def _user_text(messages: list[GenerationMessage]) -> str:
    return " ".join(message.content for message in messages if message.role == "user").strip()


def _stable_seed(*parts: str) -> int:
    digest = hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _fake_value(name: str, prop_schema: dict[str, Any], text: str, seed: int) -> Any:
    json_type = prop_schema.get("type")
    if json_type == "string":
        return _fake_string(prop_schema, text)
    if json_type == "integer":
        return int(_fake_number(name, prop_schema, seed))
    if json_type == "number":
        return _fake_number(name, prop_schema, seed)
    if json_type == "boolean":
        return _stable_seed(name, str(seed)) % 2 == 0
    if json_type == "array":
        return _fake_array(name, prop_schema, seed)
    return None


def _fake_string(prop_schema: dict[str, Any], text: str) -> str:
    min_length = prop_schema.get("minLength", 0)
    max_length = prop_schema.get("maxLength")

    value = text if text else "unknown"
    if max_length is not None:
        value = value[:max_length]
    if len(value) < min_length:
        pad = "x" * (min_length - len(value))
        value = (value + pad)[:max_length] if max_length else value + pad
    return value


def _fake_number(name: str, prop_schema: dict[str, Any], seed: int) -> float:
    minimum = prop_schema.get("minimum", 0)
    maximum = prop_schema.get("maximum", minimum + 100)
    span = max(maximum - minimum, 1)
    prop_seed = _stable_seed(name, str(seed))
    return round(minimum + (prop_seed % (span * 100)) / 100, 2)


def _fake_array(name: str, prop_schema: dict[str, Any], seed: int) -> list[Any]:
    min_items = prop_schema.get("minItems", 0)
    if min_items <= 0:
        return []
    item_schema = prop_schema.get("items", {})
    return [_fake_value(f"{name}[{i}]", item_schema, "", seed) for i in range(min_items)]
