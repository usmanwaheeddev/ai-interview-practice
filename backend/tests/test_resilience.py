import asyncio

import pytest

from app.providers.resilience import CircuitBreaker, CircuitOpenError, call_with_resilience


async def test_succeeds_on_first_try() -> None:
    calls = 0

    async def fn() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    result = await call_with_resilience(fn, provider="p", operation="op")
    assert result == "ok"
    assert calls == 1


async def test_retries_then_succeeds() -> None:
    calls = 0

    async def fn() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("transient")
        return "ok"

    result = await call_with_resilience(
        fn, provider="p", operation="op", max_retries=3, retry_base_s=0.001
    )
    assert result == "ok"
    assert calls == 3


async def test_exhausts_retries_and_raises() -> None:
    calls = 0

    async def fn() -> str:
        nonlocal calls
        calls += 1
        raise RuntimeError("always fails")

    with pytest.raises(RuntimeError, match="always fails"):
        await call_with_resilience(
            fn, provider="p", operation="op", max_retries=2, retry_base_s=0.001
        )
    assert calls == 3  # initial attempt + 2 retries


async def test_timeout_counts_as_failure() -> None:
    async def fn() -> str:
        await asyncio.sleep(10)
        return "never"

    with pytest.raises(TimeoutError):
        await call_with_resilience(fn, provider="p", operation="op", timeout_s=0.01, max_retries=0)


async def test_circuit_opens_after_threshold_failures() -> None:
    breaker = CircuitBreaker(failure_threshold=2, reset_after_s=60)

    async def failing() -> str:
        raise RuntimeError("boom")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await call_with_resilience(
                failing, provider="p", operation="op", max_retries=0, breaker=breaker
            )

    assert breaker.is_open
    with pytest.raises(CircuitOpenError):
        await call_with_resilience(failing, provider="p", operation="op", breaker=breaker)


async def test_circuit_recovers_after_reset_window() -> None:
    breaker = CircuitBreaker(failure_threshold=1, reset_after_s=0.01)

    async def failing() -> str:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await call_with_resilience(
            failing, provider="p", operation="op", max_retries=0, breaker=breaker
        )
    assert breaker.is_open

    await asyncio.sleep(0.02)
    assert not breaker.is_open  # half-open: next call is allowed through

    async def succeeding() -> str:
        return "recovered"

    result = await call_with_resilience(succeeding, provider="p", operation="op", breaker=breaker)
    assert result == "recovered"
    assert not breaker.is_open


async def test_success_resets_failure_count() -> None:
    breaker = CircuitBreaker(failure_threshold=2, reset_after_s=60)
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        # Fails once, succeeds, fails once more — should never trip the
        # breaker since a success resets the streak.
        if calls["n"] in (1, 3):
            raise RuntimeError("boom")
        return "ok"

    with pytest.raises(RuntimeError):
        await call_with_resilience(
            flaky, provider="p", operation="op", max_retries=0, breaker=breaker
        )
    await call_with_resilience(flaky, provider="p", operation="op", breaker=breaker)
    assert not breaker.is_open

    with pytest.raises(RuntimeError):
        await call_with_resilience(
            flaky, provider="p", operation="op", max_retries=0, breaker=breaker
        )
    assert not breaker.is_open  # only 1 consecutive failure, threshold is 2
