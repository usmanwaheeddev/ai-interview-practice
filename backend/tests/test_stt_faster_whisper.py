from app.core.config import get_settings
from app.providers.stt.faster_whisper import FasterWhisperSTTProvider


class _FakeSegment:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeInfo:
    def __init__(self, language: str, language_probability: float) -> None:
        self.language = language
        self.language_probability = language_probability


class _FakeWhisperModel:
    """Stands in for faster-whisper's WhisperModel — asserts it was asked to
    auto-detect (language=None) rather than forced into one, then returns a
    scripted detection result."""

    def __init__(self, detected_language: str) -> None:
        self._detected_language = detected_language
        self.hotwords = None
        self.initial_prompt = None
        self.beam_size = None
        self.language = None

    def transcribe(
        self,
        audio_f32,
        language=None,
        beam_size=1,
        hotwords=None,
        initial_prompt=None,
        condition_on_previous_text=True,
        temperature=None,
        word_timestamps=None,
        vad_filter=False,
        vad_parameters=None,
        repetition_penalty=1,
        no_repeat_ngram_size=0,
        hallucination_silence_threshold=None,
    ):
        self.language = language
        self.hotwords = hotwords
        self.initial_prompt = initial_prompt
        self.beam_size = beam_size
        self.condition_on_previous_text = condition_on_previous_text
        self.temperature = temperature
        self.word_timestamps = word_timestamps
        self.vad_filter = vad_filter
        self.no_repeat_ngram_size = no_repeat_ngram_size
        return [_FakeSegment("नमस्ते")], _FakeInfo(self._detected_language, 0.97)


async def test_auto_detect_reports_detected_language() -> None:
    provider = FasterWhisperSTTProvider(get_settings())
    provider._model = _FakeWhisperModel("hi")  # bypasses real model loading

    silence = b"\x00\x00" * 1600  # 0.1s of 16-bit mono silence at 16kHz
    transcript = await provider.transcribe(silence, sample_rate=16000, language=None)

    assert transcript.text == "नमस्ते"
    assert transcript.language == "hi"
    assert transcript.confidence == 0.97
    assert provider._model.language is None


async def test_passes_resume_vocabulary_to_whisper() -> None:
    provider = FasterWhisperSTTProvider(get_settings())
    model = _FakeWhisperModel("en")
    provider._model = model

    await provider.transcribe(
        b"\x00\x00" * 1600,
        language="en",
        hotwords="Mubashir Shaheen, FastAPI, AI chatbots",
        initial_prompt="Expected technical terms: FastAPI.",
    )

    assert model.hotwords == "Mubashir Shaheen, FastAPI, AI chatbots"
    assert model.initial_prompt == "Expected technical terms: FastAPI."
    assert model.beam_size == 1
    assert model.language == "en"
    assert model.condition_on_previous_text is False
    assert model.temperature == 0
    assert model.word_timestamps is False
    assert model.vad_filter is True
    assert model.no_repeat_ngram_size == 3
