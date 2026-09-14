"""Shared resilience wrapper for provider adapters — timeout, bounded retry
with jitter, and a circuit breaker. See architecture.md §7: free tiers
rate-limit without warning, so every adapter needs the same discipline rather
than each reinventing it.

Fake adapters (in-memory, no I/O) don't use this — nothing to be resilient
against.
"""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)


class CircuitOpenError(Exception):
    """Raised instead of attempting a call while the breaker is open."""


@dataclass
class CircuitBreaker:
    """Per-provider-instance. Opens after `failure_threshold` consecutive
    failures; refuses calls for `reset_after_s`, then allows one trial call
    (half-open) whose outcome decides whether it closes again."""

    failure_threshold: int = 3
    reset_after_s: float = 30.0
    _failures: int = field(default=0, init=False, repr=False)
    _opened_at: float | None = field(default=None, init=False, repr=False)

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self.reset_after_s:
            return False  # half-open: let the next call through as a trial
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold and self._opened_at is None:
            self._opened_at = time.monotonic()


def _backoff_with_jitter(attempt: int, base_s: float) -> float:
    delay = base_s * (2**attempt)
    return delay + random.uniform(0, delay * 0.5)


async def call_with_resilience[T](
    fn: Callable[[], Awaitable[T]],
    *,
    provider: str,
    operation: str,
    timeout_s: float = 5.0,
    max_retries: int = 2,
    retry_base_s: float = 0.2,
    breaker: CircuitBreaker | None = None,
) -> T:
    """Run `fn` under a timeout, retrying transient failures with jittered
    backoff, tracked through an optional shared CircuitBreaker.

    `fn` takes no arguments — callers close over their own args, which keeps
    this generic across LLM/STT/TTS call shapes.
    """
    if breaker is not None and breaker.is_open:
        raise CircuitOpenError(f"{provider}.{operation}: circuit open")

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(fn(), timeout=timeout_s)
        except Exception as exc:  # noqa: BLE001 — deliberately broad: any provider failure is retryable
            last_exc = exc
            if breaker is not None:
                breaker.record_failure()
            logger.warning(
                "provider.call_failed",
                provider=provider,
                operation=operation,
                attempt=attempt,
                latency_ms=round((time.monotonic() - started) * 1000),
                error=str(exc),
            )
            if attempt < max_retries:
                await asyncio.sleep(_backoff_with_jitter(attempt, retry_base_s))
            continue
        else:
            if breaker is not None:
                breaker.record_success()
            return result

    assert last_exc is not None
    raise last_exc
