"""Loose JSON extraction from LLM output. Local models routinely wrap JSON in
prose or markdown fences despite instructions not to — this tries
progressively less strict extraction rather than failing on the first
mismatch. Shared by the LLM adapters and any service that parses a
completion as structured data (e.g. interview plan generation)."""

import json
import re
from typing import Any

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


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
