"""Redis-backed live EngineState cache — architecture.md §5: "Session state
lives in Redis keyed by session_id ... so a *server* restart is survivable
too." Postgres (see persistence.py) holds the coarse session record and the
append-only turn log for audit/scoring; this is the fast, full in-flight
state the engine needs to resume mid-turn without replaying anything.

Scope note: this covers the API *process* restarting while Redis stays up
(the normal case — they're separate containers). If Redis itself is also
lost, the in-progress session's live state is gone; see memory.md for the
documented tradeoff instead of attempting turn-replay reconstruction, which
isn't sound when the Director's judgment isn't deterministic.
"""

import dataclasses
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis

from app.services.interview.director import TopicProgress
from app.services.interview.engine import EngineState

_KEY_PREFIX = "interview:engine_state:"
_DISCONNECT_KEY_PREFIX = "interview:disconnected_at:"
_TTL_S = 24 * 60 * 60  # abandoned sessions shouldn't linger in Redis forever


def _key(session_id: uuid.UUID) -> str:
    return f"{_KEY_PREFIX}{session_id}"


def _disconnect_key(session_id: uuid.UUID) -> str:
    return f"{_DISCONNECT_KEY_PREFIX}{session_id}"


def _serialize(state: EngineState) -> str:
    payload = dataclasses.asdict(state)
    return json.dumps(payload)


def _deserialize(raw: str) -> EngineState:
    payload: dict[str, Any] = json.loads(raw)
    progress = TopicProgress(**payload.pop("progress"))
    return EngineState(progress=progress, **payload)


async def save_state(redis: Redis, session_id: uuid.UUID, state: EngineState) -> None:
    await redis.set(_key(session_id), _serialize(state), ex=_TTL_S)


async def load_state(redis: Redis, session_id: uuid.UUID) -> EngineState | None:
    raw = await redis.get(_key(session_id))
    if raw is None:
        return None
    return _deserialize(raw)


async def clear_state(redis: Redis, session_id: uuid.UUID) -> None:
    await redis.delete(_key(session_id))


async def mark_disconnected(redis: Redis, session_id: uuid.UUID) -> None:
    await redis.set(_disconnect_key(session_id), datetime.now(UTC).isoformat(), ex=_TTL_S)


async def pop_disconnected_at(redis: Redis, session_id: uuid.UUID) -> datetime | None:
    """Read and clear in one call — a reconnect should only charge grace
    once per disconnect, not once per session.start retry."""
    raw = await redis.get(_disconnect_key(session_id))
    if raw is None:
        return None
    await redis.delete(_disconnect_key(session_id))
    return datetime.fromisoformat(raw)
