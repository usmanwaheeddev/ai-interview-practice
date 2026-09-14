"""Contract tests against real self-hosted provider infra (Ollama,
faster-whisper, Piper). Slow (model load), requires the docker-compose stack
running with OLLAMA_URL reachable — not run in CI. Run explicitly:

    docker compose exec api pytest -m contract tests/contract/

See skills.md `add-provider-adapter` for why these are separate from the main
suite: real APIs are slow, occasionally flaky, and non-deterministic — the
main suite runs against `fake` adapters exclusively (plan.md §3.7).
"""

import pytest

from app.core.config import get_settings
from app.providers.llm.groq import GroqLLMProvider
from app.providers.llm.ollama import OllamaLLMProvider
from app.providers.stt.faster_whisper import FasterWhisperSTTProvider
from app.providers.tts.piper import PiperTTSProvider

pytestmark = pytest.mark.contract


async def test_ollama_health() -> None:
    provider = OllamaLLMProvider(get_settings())
    assert await provider.health() is True


async def test_ollama_completes_a_prompt() -> None:
    provider = OllamaLLMProvider(get_settings())
    response = await provider.complete(
        system="Reply with exactly one word.", user="Say the word 'hello'."
    )
    assert isinstance(response, str)
    assert len(response.strip()) > 0


async def test_groq_health() -> None:
    provider = GroqLLMProvider(get_settings())
    assert await provider.health() is True


async def test_groq_completes_a_prompt() -> None:
    provider = GroqLLMProvider(get_settings())
    response = await provider.complete(
        system="Reply with exactly one word.", user="Say the word 'hello'."
    )
    assert isinstance(response, str)
    assert len(response.strip()) > 0


async def test_faster_whisper_health() -> None:
    provider = FasterWhisperSTTProvider(get_settings())
    assert await provider.health() is True


async def test_piper_health() -> None:
    provider = PiperTTSProvider(get_settings())
    assert await provider.health() is True


async def test_piper_synthesizes_nonempty_wav() -> None:
    provider = PiperTTSProvider(get_settings())
    wav_bytes = await provider.synthesize("This is a test.")
    assert wav_bytes.startswith(b"RIFF")
    assert len(wav_bytes) > 44  # more than just a WAV header


async def test_round_trip_tts_then_stt_recovers_similar_text() -> None:
    """Synthesize a sentence, transcribe it back, and check for a rough word
    overlap — not exact-match (TTS/STT aren't lossless), just "the pipeline
    actually does something coherent, not garbage"."""
    import io
    import wave

    tts = PiperTTSProvider(get_settings())
    stt = FasterWhisperSTTProvider(get_settings())

    original = "The quick brown fox jumps over the lazy dog"
    wav_bytes = await tts.synthesize(original)

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        pcm = wf.readframes(wf.getnframes())
        rate = wf.getframerate()

    transcript = await stt.transcribe(pcm, sample_rate=rate)

    original_words = set(original.lower().split())
    heard_words = set(transcript.text.lower().split())
    overlap = original_words & heard_words
    assert len(overlap) >= len(original_words) // 2, (
        f"expected rough overlap, got heard={transcript.text!r}"
    )
