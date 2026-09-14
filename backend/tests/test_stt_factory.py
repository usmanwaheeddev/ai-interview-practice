import app.providers.stt as stt_factory
from app.core.config import Settings
from app.providers.stt.fake import FakeSTTProvider
from app.providers.stt.faster_whisper import FasterWhisperSTTProvider
from app.providers.stt.whisper_cpp import WhisperCppEngine


def _select(monkeypatch, settings: Settings):
    stt_factory.get_stt_engine.cache_clear()
    monkeypatch.setattr(stt_factory, "get_settings", lambda: settings)
    return stt_factory.get_stt_engine()


def test_faster_whisper_is_default_engine(monkeypatch) -> None:
    engine = _select(monkeypatch, Settings(stt_provider="faster_whisper"))
    assert isinstance(engine, FasterWhisperSTTProvider)


def test_whisper_cpp_is_selectable(monkeypatch) -> None:
    engine = _select(
        monkeypatch,
        Settings(stt_provider="faster_whisper", stt_engine="whisper_cpp"),
    )
    assert isinstance(engine, WhisperCppEngine)


def test_fake_provider_still_bypasses_engine_selection(monkeypatch) -> None:
    engine = _select(
        monkeypatch,
        Settings(stt_provider="fake", stt_engine="whisper_cpp"),
    )
    assert isinstance(engine, FakeSTTProvider)
