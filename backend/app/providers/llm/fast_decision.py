"""Shared contract for the latency-sensitive live interview decision."""

from typing import Any

FAST_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["advance", "follow_up", "clarify"],
        },
        "text": {"type": "string"},
    },
    "required": ["action", "text"],
    "additionalProperties": False,
}

FAST_DECISION_MAX_TOKENS = 96
FAST_DECISION_TIMEOUT_S = 15.0

