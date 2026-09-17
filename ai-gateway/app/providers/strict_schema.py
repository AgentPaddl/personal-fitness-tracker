"""Translate a JSON Schema without weakening the caller's original validation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_LOCAL_ONLY = {
    "default", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "multipleOf", "minLength", "maxLength", "pattern", "format", "minItems",
    "maxItems", "uniqueItems", "minProperties", "maxProperties",
}
_SUPPORTED = {
    "type", "properties", "required", "additionalProperties", "items", "enum",
    "anyOf", "$defs", "$ref", "title", "description",
}
_TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}


def to_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    if schema.get("type") != "object" or "anyOf" in schema:
        raise ValueError("A structured result must have an object root.")

    def translate(node: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(node, dict) or node.keys() - _LOCAL_ONLY - _SUPPORTED:
            raise ValueError("Unsupported structured output schema.")
        result = {key: deepcopy(value) for key, value in node.items() if key not in _LOCAL_ONLY}
        if "$ref" in node:
            reference = node["$ref"]
            if not isinstance(reference, str) or not reference.startswith("#/$defs/"):
                raise ValueError("Only local definition references are supported.")
            target = schema
            try:
                for segment in reference[2:].split("/"):
                    target = target[segment.replace("~1", "/").replace("~0", "~")]
            except (KeyError, TypeError):
                raise ValueError("Unresolved structured output reference.") from None
            if not isinstance(target, dict):
                raise ValueError("Invalid structured output reference.")
        node_types = node.get("type", [])
        if isinstance(node_types, str):
            node_types = [node_types]
        if not isinstance(node_types, list) or any(kind not in _TYPES for kind in node_types):
            raise ValueError("Unsupported structured output type.")
        if "object" in node_types:
            if isinstance(node.get("additionalProperties"), dict):
                raise ValueError("Open-ended dictionaries are not supported.")
            properties = node.get("properties", {})
            result["properties"] = {name: translate(value) for name, value in properties.items()}
            result["required"] = list(properties)
            result["additionalProperties"] = False
        if "array" in node_types:
            result["items"] = translate(node.get("items"))
        if "anyOf" in node:
            result["anyOf"] = [translate(variant) for variant in node["anyOf"]]
        if "$defs" in node:
            result["$defs"] = {name: translate(value) for name, value in node["$defs"].items()}
        return result

    return translate(schema)