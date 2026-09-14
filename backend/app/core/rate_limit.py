"""Redis-backed fixed-window rate limiting — Phase 6 hardening pass
(phases.md: "per-IP auth, per-user applications, per-org concurrent
interviews"). Fixed-window, not sliding/token-bucket: simpler, and the
difference doesn't matter at these limits — nobody's budgeting requests
down to the second here, just capping abuse.
"""

from redis.asyncio import Redis

from app.core.exceptions import TooManyRequestsError


async def enforce_rate_limit(
    redis: Redis, *, key: str, limit: int, window_s: int, message: str
) -> None:
    """Raises TooManyRequestsError once `key` has been hit more than `limit`
    times within the current `window_s`-second window. The window is a
    single Redis key with a TTL, incremented atomically — one round trip,
    no Lua script needed at this scale."""
    full_key = f"ratelimit:{key}"
    count = await redis.incr(full_key)
    if count == 1:
        await redis.expire(full_key, window_s)
    if count > limit:
        raise TooManyRequestsError(message, code="rate_limited")
