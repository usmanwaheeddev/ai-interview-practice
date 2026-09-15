from collections.abc import AsyncIterator
from typing import Any, Protocol


class LLMProvider(Protocol):
    """extract_json: Phase 1's resume-extraction slice.
    complete: Phase 2's interview-director slice — a single free-form
    completion, used both by the Director (Phase 3) and by the latency
    harness to measure a representative "decide next question" call.
    stream_complete: same shape as `complete` but yields text chunks as they
    arrive. See app/providers/llm/fallback.py's
    `FallbackLLMProvider` for the configured Ollama/Groq ordering wrapping
    every method here, applied at `get_llm_provider()`.
    """

    async def extract_json(
        self,
        *,
        prompt: str,
        text: str,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    async def complete(self, *, system: str, user: str, max_tokens: int = 60) -> str: ...

    def stream_complete(
        self, *, system: str, user: str, max_tokens: int = 500
    ) -> AsyncIterator[str]: ...

    async def health(self) -> bool: ...
