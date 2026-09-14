from collections.abc import AsyncIterator
from functools import lru_cache

from app.core.config import get_settings
from app.providers.llm.base import LLMProvider
from app.providers.llm.fake import FakeLLMProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    """The single source of truth for "the" LLM provider — every caller
    (interview plan generation, the Director, resume extraction, report
    scoring, coding-hint/review streaming) gets whatever this returns, so
    wrapping it once here is enough to give all of them the same behavior.

    `LLM_PROVIDER` chooses which real provider is tried first. The other real
    provider remains its fallback, so switching priority does not sacrifice
    resilience.
    """
    settings = get_settings()
    if settings.llm_provider == "fake":
        return FakeLLMProvider()

    if settings.llm_provider == "ollama":
        from app.providers.llm.fallback import FallbackLLMProvider
        from app.providers.llm.groq import GroqLLMProvider
        from app.providers.llm.ollama import OllamaLLMProvider

        return FallbackLLMProvider(
            primary=OllamaLLMProvider(settings),
            fallback=GroqLLMProvider(settings),
            primary_name="ollama",
            fallback_name="groq",
            primary_json_timeout_s=150.0,
            fallback_json_timeout_s=30.0,
        )

    if settings.llm_provider == "groq":
        from app.providers.llm.fallback import FallbackLLMProvider
        from app.providers.llm.groq import GroqLLMProvider
        from app.providers.llm.ollama import OllamaLLMProvider

        return FallbackLLMProvider(
            primary=GroqLLMProvider(settings),
            fallback=OllamaLLMProvider(settings),
            primary_name="groq",
            fallback_name="ollama",
            primary_json_timeout_s=30.0,
            fallback_json_timeout_s=150.0,
        )

    raise NotImplementedError(
        f"LLM provider '{settings.llm_provider}' is not wired up. "
        "Use 'fake', 'ollama' or 'groq' — see phases.md Phase 2 / architecture.md §7."
    )


async def stream_complete_with_fallback(
    *, system: str, user: str, max_tokens: int = 500
) -> AsyncIterator[str]:
    """Thin pass-through kept as the coding-challenge streaming routes'
    stable import — see app/api/coding.py. The fallback itself now lives in
    whatever `get_llm_provider()` returns, not here."""
    async for chunk in get_llm_provider().stream_complete(
        system=system, user=user, max_tokens=max_tokens
    ):
        yield chunk
