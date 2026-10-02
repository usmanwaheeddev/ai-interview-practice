from functools import lru_cache

from app.core.config import get_settings
from app.providers.llm.base import LLMProvider
from app.providers.llm.fake import FakeLLMProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    """Build the configured LLM: DeepSeek primary with Ollama fallback."""
    settings = get_settings()

    if settings.llm_provider == "fake":
        return FakeLLMProvider()

    if settings.llm_provider == "deepseek":
        if not settings.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is required when LLM_PROVIDER=deepseek")
        from app.providers.llm.deepseek import DeepSeekLLMProvider
        from app.providers.llm.fallback import FallbackLLMProvider
        from app.providers.llm.ollama import OllamaLLMProvider

        return FallbackLLMProvider(
            primary=DeepSeekLLMProvider(settings),
            fallback=OllamaLLMProvider(settings),
            primary_name="deepseek",
            fallback_name="ollama",
            primary_json_timeout_s=530.0,
            fallback_json_timeout_s=150.0,
        )

    if settings.llm_provider == "ollama":
        from app.providers.llm.ollama import OllamaLLMProvider

        return OllamaLLMProvider(settings)

    raise NotImplementedError(
        f"LLM provider '{settings.llm_provider}' is not wired up. "
        "Use 'deepseek', 'ollama', or 'fake'."
    )
