import uuid
from datetime import UTC, datetime
from typing import Any

from app.services.interview.director import TopicProgress
from app.services.interview.engine import EngineState
from app.services.interview.state_store import (
    clear_state,
    load_state,
    mark_disconnected,
    pop_disconnected_at,
    save_state,
)


class FakeRedis:
    """Minimal stand-in for redis.asyncio.Redis — just enough of get/set/delete
    to test our serialization round-trip without a real Redis server. Real
    Redis behaviour (TTL expiry, connection handling) is out of scope for a
    unit test — see plan.md §3.7."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def set(self, key: str, value: str, *, ex: int | None = None) -> None:
        self._store[key] = value

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


async def test_save_and_load_round_trip() -> None:
    redis: Any = FakeRedis()
    session_id = uuid.uuid4()
    state = EngineState(
        topic_index=2,
        progress=TopicProgress(follow_ups_used=1, block_elapsed_s=45),
        elapsed_s=300,
        turn_index=7,
        in_candidate_questions=False,
        complete=False,
        current_block_started_at_s=200,
    )

    await save_state(redis, session_id, state)
    loaded = await load_state(redis, session_id)

    assert loaded == state


async def test_load_missing_state_returns_none() -> None:
    redis: Any = FakeRedis()
    result = await load_state(redis, uuid.uuid4())
    assert result is None


async def test_clear_state_removes_it() -> None:
    redis: Any = FakeRedis()
    session_id = uuid.uuid4()
    await save_state(redis, session_id, EngineState())

    await clear_state(redis, session_id)
    assert await load_state(redis, session_id) is None


async def test_different_sessions_do_not_collide() -> None:
    redis: Any = FakeRedis()
    a, b = uuid.uuid4(), uuid.uuid4()

    await save_state(redis, a, EngineState(elapsed_s=10))
    await save_state(redis, b, EngineState(elapsed_s=20))

    loaded_a = await load_state(redis, a)
    loaded_b = await load_state(redis, b)
    assert loaded_a is not None and loaded_a.elapsed_s == 10
    assert loaded_b is not None and loaded_b.elapsed_s == 20


async def test_disconnect_timestamp_round_trip() -> None:
    redis: Any = FakeRedis()
    session_id = uuid.uuid4()

    before = datetime.now(UTC)
    await mark_disconnected(redis, session_id)
    after = datetime.now(UTC)

    popped = await pop_disconnected_at(redis, session_id)
    assert popped is not None
    assert before <= popped <= after


async def test_pop_disconnected_at_clears_it() -> None:
    redis: Any = FakeRedis()
    session_id = uuid.uuid4()
    await mark_disconnected(redis, session_id)

    await pop_disconnected_at(redis, session_id)
    assert await pop_disconnected_at(redis, session_id) is None


async def test_pop_disconnected_at_missing_returns_none() -> None:
    redis: Any = FakeRedis()
    assert await pop_disconnected_at(redis, uuid.uuid4()) is None
