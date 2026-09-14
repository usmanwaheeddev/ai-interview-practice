from functools import lru_cache

from app.core.config import get_settings
from app.providers.stt.base import STTProvider
from app.providers.stt.fake import FakeSTTProvider


@lru_cache
def get_stt_engine() -> STTProvider:
    settings = get_settings()
    if settings.stt_provider == "fake":
        return FakeSTTProvider()

    if settings.stt_provider != "faster_whisper":
        raise NotImplementedError(
            f"STT provider '{settings.stt_provider}' is not wired up. "
            "Use 'fake' or 'faster_whisper'."
        )

    if settings.stt_engine == "faster_whisper":
        from app.providers.stt.faster_whisper import FasterWhisperSTTProvider

        return FasterWhisperSTTProvider(settings)

    if settings.stt_engine == "whisper_cpp":
        from app.providers.stt.whisper_cpp import WhisperCppEngine

        return WhisperCppEngine(settings)

    raise NotImplementedError(
        f"STT engine '{settings.stt_engine}' is not wired up. "
        "Use 'faster_whisper' or 'whisper_cpp'."
    )


def get_stt_provider() -> STTProvider:
    """Backward-compatible factory name used by existing callers."""
    return get_stt_engine()
