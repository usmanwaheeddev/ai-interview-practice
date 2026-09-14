from functools import lru_cache

from app.core.config import get_settings
from app.providers.tts.base import TTSProvider
from app.providers.tts.fake import FakeTTSProvider


@lru_cache
def get_tts_provider() -> TTSProvider:
    settings = get_settings()
    if settings.tts_provider == "fake":
        return FakeTTSProvider()

    if settings.tts_provider == "piper":
        from app.providers.tts.piper import PiperTTSProvider

        return PiperTTSProvider(settings)

    raise NotImplementedError(
        f"TTS provider '{settings.tts_provider}' is not wired up. "
        "Use 'fake' or 'piper' — see phases.md Phase 2 / architecture.md §7."
    )
