from redis.asyncio import Redis, from_url

from app.core.config import get_settings

_client: Redis | None = None


def get_redis() -> Redis:
    """Lazily-created, cached Redis client — separate from the ARQ pool
    (app/core/queue.py), which is for job enqueueing, not general key-value
    access."""
    global _client
    if _client is None:
        # decode_responses=True: every value this client reads/writes is
        # text (JSON, ISO timestamps) — see state_store.py's
        # `datetime.fromisoformat`, which raises TypeError on the raw bytes
        # redis-py returns by default. Caught live in Phase 4 browser
        # testing on the reconnect path; see memory.md.
        _client = from_url(get_settings().redis_url, decode_responses=True)
    return _client
