import os

# Must happen before any `app.*` import — several modules call get_settings()
# at import time (it's lru_cache'd, so whatever's read first sticks for the
# whole test process). Forces tests onto in-memory fakes, never real infra —
# see plan.md §3.7 and skills.md `generate-synthetic-candidate`.
os.environ["STORAGE_PROVIDER"] = "fake"
os.environ["LLM_PROVIDER"] = "fake"
os.environ["STT_PROVIDER"] = "fake"
os.environ["TTS_PROVIDER"] = "fake"

from collections.abc import AsyncIterator  # noqa: E402
from typing import Any  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.queue import get_queue  # noqa: E402
from app.core.redis import get_redis  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db, get_session_factory  # noqa: E402
from app.main import app  # noqa: E402

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class FakeQueue:
    """Records enqueued jobs instead of touching real Redis/ARQ."""

    def __init__(self) -> None:
        self.enqueued: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, function: str, *args: Any) -> None:
        self.enqueued.append((function, args))


class FakeRedis:
    """A real fixed-window counter (incr/expire), backed by a dict instead
    of Redis — used everywhere `get_redis` is overridden so tests never
    touch the real, shared, cross-test-persistent Redis instance. Phase 6
    added `enforce_rate_limit` (`app/core/rate_limit.py`) calls on
    `/auth/login`, `/auth/register/*` and `/applications` — without this,
    every test hitting those enough times across a full suite run shares
    real rate-limit counters and starts failing with 429s that have nothing
    to do with what that test is actually checking."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        pass

    async def ping(self) -> bool:
        return True


@pytest.fixture
async def _test_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Bound to a single per-test engine so every session it produces —
    `db_session` below, and any extra one a StreamingResponse generator
    opens via `get_session_factory` (see app/db/session.py's docstring for
    why that dependency exists) — shares the same in-memory SQLite database."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=StaticPool)

    # SQLite does not enforce foreign keys (ON DELETE CASCADE included)
    # unless told to, per connection — unlike Postgres, where it's always
    # on. Without this, `db.delete(parent)` silently leaves every
    # `ondelete="CASCADE"` child row behind on SQLite while behaving
    # correctly against the real Postgres this stands in for (plan.md
    # §3.7) — a real gap, not a hypothetical one: it's exactly what broke
    # `test_compliance_purge.py`'s cascade-delete assertions before this
    # was added.
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_fk(dbapi_connection: Any, _: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield async_sessionmaker(engine, expire_on_commit=False)

    await engine.dispose()


@pytest.fixture
async def db_session(
    _test_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with _test_session_factory() as session:
        yield session


@pytest.fixture
def fake_queue() -> FakeQueue:
    return FakeQueue()


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


def _apply_overrides(
    db_session: AsyncSession,
    fake_queue: FakeQueue,
    fake_redis: FakeRedis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    async def override_get_queue() -> FakeQueue:
        return fake_queue

    async def override_get_redis() -> FakeRedis:
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_queue] = override_get_queue
    app.dependency_overrides[get_redis] = override_get_redis
    # Same per-test engine as `db_session` (see _test_session_factory) —
    # code that opens its own session later, e.g. a StreamingResponse
    # generator, still lands on the test database, not the real one.
    app.dependency_overrides[get_session_factory] = lambda: session_factory


@pytest.fixture
async def client(
    db_session: AsyncSession,
    fake_queue: FakeQueue,
    fake_redis: FakeRedis,
    _test_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    _apply_overrides(db_session, fake_queue, fake_redis, _test_session_factory)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def client_factory(
    db_session: AsyncSession,
    fake_queue: FakeQueue,
    fake_redis: FakeRedis,
    _test_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[Any]:
    """Multi-actor tests (HR + candidate acting in the same test) need
    separate cookie jars — one AsyncClient each, all pointed at the same
    app/db so they observe each other's writes."""
    _apply_overrides(db_session, fake_queue, fake_redis, _test_session_factory)

    clients: list[AsyncClient] = []

    async def _make() -> AsyncClient:
        transport = ASGITransport(app=app)
        c = AsyncClient(transport=transport, base_url="https://test")
        clients.append(c)
        return c

    yield _make

    for c in clients:
        await c.aclose()
    app.dependency_overrides.clear()
