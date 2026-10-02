from collections.abc import AsyncIterator
from typing import Any, Protocol


class LLMProvider(Protocol):
    """extract_json: Phase 1's resume-extraction slice.
    complete: general free-form generation used by scoring and diagnostics.
    fast_decide: the bounded structured call used by the live Director and
    latency harness.
    stream_complete: same shape as `complete` but yields text chunks as they
    arrive. See app/providers/llm/fallback.py's
    `FallbackLLMProvider` for the configured
    DeepSeek-to-Ollama fallback wrapping,
    applied at `get_llm_provider()`.
    """

    async def extract_json(
        self,
        *,
        prompt: str,
        text: str,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    async def complete(self, *, system: str, user: str, max_tokens: int = 60) -> str: ...

    async def fast_decide(self, *, system: str, user: str) -> dict[str, Any]: ...

    def stream_complete(
        self, *, system: str, user: str, max_tokens: int = 500
    ) -> AsyncIterator[str]: ...

    async def health(self) -> bool: ...
