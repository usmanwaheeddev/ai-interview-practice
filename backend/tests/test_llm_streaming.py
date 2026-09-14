import pytest

from app.core.config import get_settings
from app.providers.llm import get_llm_provider, stream_complete_with_fallback
from app.providers.llm.fake import FakeLLMProvider
from app.providers.llm.fallback import FallbackLLMProvider


async def test_fake_provider_streams_chunks():
    provider = FakeLLMProvider()
    chunks = [c async for c in provider.stream_complete(system="s", user="hello world")]
    assert len(chunks) > 1
    assert "".join(chunks).strip() == "[fake streamed completion for: hello world]"


class _FailsBeforeFirstChunk:
    async def complete(self, *, system, user, max_tokens=60):
        raise RuntimeError("connection refused")

    async def extract_json(self, *, prompt, text, json_schema=None):
        raise RuntimeError("connection refused")

    async def stream_complete(self, *, system, user, max_tokens=500):
        raise RuntimeError("connection refused")
        yield  # pragma: no cover - makes this an async generator

    async def health(self) -> bool:
        return False


class _FailsAfterFirstChunk:
    async def stream_complete(self, *, system, user, max_tokens=500):
        yield "partial "
        raise RuntimeError("stream dropped")


class _Succeeds:
    async def complete(self, *, system, user, max_tokens=60) -> str:
        return "fallback response"

    async def extract_json(self, *, prompt, text, json_schema=None) -> dict:
        return {"ok": True}

    async def stream_complete(self, *, system, user, max_tokens=500):
        yield "fallback "
        yield "response"

    async def health(self) -> bool:
        return True


async def test_fallback_complete_used_when_primary_fails():
    provider = FallbackLLMProvider(primary=_FailsBeforeFirstChunk(), fallback=_Succeeds())
    assert await provider.complete(system="s", user="u") == "fallback response"


async def test_fallback_extract_json_used_when_primary_fails():
    provider = FallbackLLMProvider(primary=_FailsBeforeFirstChunk(), fallback=_Succeeds())
    assert await provider.extract_json(prompt="p", text="t") == {
        "ok": True,
        "_provider": "ollama",
    }


async def test_fallback_not_used_when_primary_succeeds():
    """A fallback that would raise if ever called proves the primary's
    result is returned directly, not silently replaced."""

    class ExplodingFallback:
        async def complete(self, *, system, user, max_tokens=60):
            raise AssertionError("fallback should not be called when primary succeeds")

    provider = FallbackLLMProvider(primary=_Succeeds(), fallback=ExplodingFallback())
    assert await provider.complete(system="s", user="u") == "fallback response"


async def test_fallback_stream_switches_provider_when_primary_fails_before_any_chunk():
    provider = FallbackLLMProvider(primary=_FailsBeforeFirstChunk(), fallback=_Succeeds())
    chunks = [c async for c in provider.stream_complete(system="s", user="u")]
    assert "".join(chunks) == "fallback response"


async def test_fallback_stream_no_switch_after_partial_output_already_sent():
    """A failure partway through must propagate, not silently switch
    providers — that would produce inconsistent/duplicated output."""
    provider = FallbackLLMProvider(primary=_FailsAfterFirstChunk(), fallback=_Succeeds())
    collected = []
    with pytest.raises(RuntimeError, match="stream dropped"):
        async for chunk in provider.stream_complete(system="s", user="u"):
            collected.append(chunk)
    assert collected == ["partial "]


async def test_fallback_health_true_if_either_provider_is_healthy():
    class Unhealthy:
        async def health(self) -> bool:
            return False

    class Healthy:
        async def health(self) -> bool:
            return True

    assert await FallbackLLMProvider(primary=Unhealthy(), fallback=Healthy()).health() is True
    assert await FallbackLLMProvider(primary=Unhealthy(), fallback=Unhealthy()).health() is False


async def test_get_llm_provider_wraps_groq_with_fallback(monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_provider", "groq")
    get_llm_provider.cache_clear()
    try:
        assert isinstance(get_llm_provider(), FallbackLLMProvider)
    finally:
        get_llm_provider.cache_clear()


async def test_get_llm_provider_wraps_ollama_with_groq_fallback(monkeypatch):
    from app.providers.llm.ollama import OllamaLLMProvider

    monkeypatch.setattr(get_settings(), "llm_provider", "ollama")
    get_llm_provider.cache_clear()
    try:
        provider = get_llm_provider()
        assert isinstance(provider, FallbackLLMProvider)
        assert isinstance(provider._primary, OllamaLLMProvider)
        assert provider._primary_name == "ollama"
        assert provider._fallback_name == "groq"
    finally:
        get_llm_provider.cache_clear()


async def test_stream_complete_with_fallback_delegates_to_llm_provider(monkeypatch):
    import app.providers.llm as llm_module

    monkeypatch.setattr(llm_module, "get_llm_provider", lambda: _Succeeds())
    chunks = [c async for c in stream_complete_with_fallback(system="s", user="u")]
    assert "".join(chunks) == "fallback response"
