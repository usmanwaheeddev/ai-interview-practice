from typing import Any

import pytest

from app.core.exceptions import TooManyRequestsError
from app.core.rate_limit import enforce_rate_limit
from tests.conftest import FakeRedis


async def test_allows_requests_under_the_limit() -> None:
    redis: Any = FakeRedis()
    for _ in range(5):
        await enforce_rate_limit(redis, key="test", limit=5, window_s=60, message="too many")


async def test_rejects_requests_over_the_limit() -> None:
    redis: Any = FakeRedis()
    for _ in range(5):
        await enforce_rate_limit(redis, key="test2", limit=5, window_s=60, message="too many")

    with pytest.raises(TooManyRequestsError):
        await enforce_rate_limit(redis, key="test2", limit=5, window_s=60, message="too many")


async def test_different_keys_have_independent_limits() -> None:
    redis: Any = FakeRedis()
    for _ in range(5):
        await enforce_rate_limit(redis, key="a", limit=5, window_s=60, message="too many")
    # key "b" hasn't been touched — should still be allowed.
    await enforce_rate_limit(redis, key="b", limit=5, window_s=60, message="too many")


async def test_login_rate_limit_returns_429(client: Any, fake_redis: FakeRedis) -> None:
    """Integration-level check against the real endpoint, not just the unit
    — confirms `enforce_rate_limit` is actually wired into `/auth/login`.
    `fake_redis` is the same instance `client` already uses (conftest.py
    overrides `get_redis` with it app-wide) — no manual override needed."""
    for _ in range(10):
        await client.post(
            "/api/auth/login", json={"email": "nobody@example.com", "password": "wrong"}
        )
    res = await client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "wrong"}
    )
    assert res.status_code == 429
    assert res.json()["code"] == "rate_limited"
