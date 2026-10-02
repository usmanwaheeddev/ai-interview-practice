"""Loose JSON extraction from LLM output. Local models routinely wrap JSON in
prose or markdown fences despite instructions not to — this tries
progressively less strict extraction rather than failing on the first
mismatch. Shared by the LLM adapters and any service that parses a
completion as structured data (e.g. interview plan generation)."""

import json
import re
from typing import Any

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def validate_json_result(
    parsed: dict[str, Any],
    schema: dict[str, Any] | None,
    *,
    provider: str,
) -> dict[str, Any]:
    """Reject structured output that cannot satisfy the requested schema."""
    if not isinstance(parsed, dict):
        raise ValueError(f"{provider} returned JSON that is not an object")
    if not parsed:
        raise ValueError(f"{provider} returned an empty JSON object")
    if schema is None:
        return parsed

    missing = [key for key in schema.get("required", []) if key not in parsed]
    if missing:
        raise ValueError(f"{provider} response is missing required fields: {', '.join(missing)}")

    for key, property_schema in schema.get("properties", {}).items():
        if key not in parsed:
            continue
        value = parsed[key]
        expected = property_schema.get("type")
        valid = (
            (expected == "string" and isinstance(value, str))
            or (expected == "array" and isinstance(value, list))
            or (expected == "object" and isinstance(value, dict))
            or (expected == "integer" and isinstance(value, int) and not isinstance(value, bool))
            or (
                expected == "number"
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
            )
            or expected is None
        )
        if not valid:
            raise ValueError(
                f"{provider} response field '{key}' has invalid type "
                f"{type(value).__name__}; expected {expected}"
            )

        if expected == "array":
            item_schema = property_schema.get("items", {})
            if item_schema.get("type") == "string" and not all(
                isinstance(item, str) for item in value
            ):
                raise ValueError(f"{provider} response field '{key}' contains non-string items")
            if len(value) < property_schema.get("minItems", 0):
                raise ValueError(f"{provider} response field '{key}' has too few items")
            if "maxItems" in property_schema and len(value) > property_schema["maxItems"]:
                raise ValueError(f"{provider} response field '{key}' has too many items")

        if expected in {"integer", "number"}:
            if "minimum" in property_schema and value < property_schema["minimum"]:
                raise ValueError(f"{provider} response field '{key}' is below the minimum")
            if "maximum" in property_schema and value > property_schema["maximum"]:
                raise ValueError(f"{provider} response field '{key}' exceeds the maximum")

    return parsed


def parse_json_loosely(raw: str) -> dict[str, Any]:
    for candidate in (raw, _extract_fence(raw), _extract_braces(raw)):
        if candidate is None:
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return {}


def _extract_fence(raw: str) -> str | None:
    match = _JSON_FENCE_RE.search(raw)
    return match.group(1) if match else None


def _extract_braces(raw: str) -> str | None:
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return raw[start : end + 1]
