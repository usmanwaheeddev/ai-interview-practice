import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np

from app.core.config import Settings
from app.core.logging import get_logger
from app.providers.resilience import CircuitBreaker, call_with_resilience
from app.providers.stt.base import Transcript
from app.services.audio import STT_SAMPLE_RATE, resample_pcm16_mono

logger = get_logger(__name__)


class FasterWhisperSTTProvider:
    """Local, self-hosted, no API key — see memory.md ADR-014. CPU inference
    via faster-whisper/CTranslate2. Model loads lazily (and slowly, on first
    call — downloads on first-ever run) so app startup isn't blocked by it."""

    def __init__(self, settings: Settings) -> None:
        # STT_MODEL_SIZE is the engine-neutral override. When absent, retain
        # the legacy WHISPER_MODEL_SIZE behavior unchanged.
        self._model_size = settings.stt_model_size or settings.whisper_model_size
        self._cpu_threads = settings.whisper_cpu_threads
        self._beam_size = settings.whisper_beam_size
        self._segment_timeout_s = settings.whisper_segment_timeout_s
        # faster-whisper ships no type stubs — WhisperModel resolves to Any.
        self._model: Any = None
        self._load_lock = asyncio.Lock()
        # A timed-out native CTranslate2 call keeps running. A dedicated
        # single-worker executor guarantees that later calls queue behind it
        # instead of starting competing decoders and causing a timeout spiral.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whisper")
        self._breaker = CircuitBreaker()

    async def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        async with self._load_lock:
            if self._model is not None:
                return
            logger.info("faster_whisper.loading", model_size=self._model_size)

            def _load() -> Any:
                from faster_whisper import WhisperModel

                return WhisperModel(
                    self._model_size,
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=self._cpu_threads,
                )

            self._model = await asyncio.to_thread(_load)
            logger.info("faster_whisper.loaded", model_size=self._model_size)

    def _transcribe_sync(
        self,
        audio_f32: np.ndarray,
        language: str | None,
        hotwords: str | None,
        initial_prompt: str | None,
    ) -> Transcript:
        """Runs entirely inside a worker thread. faster-whisper's `segments`
        return value is a lazy generator — decoding happens as it's iterated,
        so that iteration must stay off the event loop too, not just the
        initial `.transcribe()` call. `language=None` asks Whisper to detect
        the spoken language itself instead of forcing one; the result comes
        back on `info.language`, which the WS handler uses to auto-switch the
        conversation's language turn by turn."""
        assert self._model is not None
        segments, info = self._model.transcribe(
            audio_f32,
            language=language,
            beam_size=self._beam_size,
            hotwords=hotwords,
            initial_prompt=initial_prompt,
            # Each overlapping segment already receives the assembled text
            # as an explicit prompt. Carrying Whisper's internal previous
            # segment state as well increases hallucination/repetition risk.
            condition_on_previous_text=False,
            temperature=0,
            word_timestamps=False,
            # Apply model-level speech filtering in addition to the streaming
            # VAD. Vocabulary prompts can otherwise turn fan noise or echo
            # into repeated technical terms with high apparent confidence.
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500, "speech_pad_ms": 200},
            repetition_penalty=1.1,
            no_repeat_ngram_size=3,
            hallucination_silence_threshold=1.0,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        return Transcript(
            text=text,
            confidence=getattr(info, "language_probability", None),
            language=getattr(info, "language", None),
        )

    async def transcribe(
        self,
        audio: bytes,
        *,
        sample_rate: int = 16000,
        language: str | None = None,
        hotwords: str | None = None,
        initial_prompt: str | None = None,
    ) -> Transcript:
        await self._ensure_loaded()
        # The model expects 16 kHz — resample here so callers can hand in
        # audio at whatever rate they actually captured or synthesized it at.
        pcm_16k = resample_pcm16_mono(audio, from_rate=sample_rate, to_rate=STT_SAMPLE_RATE)
        audio_f32 = np.frombuffer(pcm_16k, dtype=np.int16).astype(np.float32) / 32768.0

        async def _call() -> Transcript:
            return await asyncio.get_running_loop().run_in_executor(
                self._executor,
                self._transcribe_sync,
                audio_f32,
                language,
                hotwords,
                initial_prompt,
            )

        return await call_with_resilience(
            _call,
            provider="faster_whisper",
            operation="transcribe",
            # A timed-out transcription keeps running in its worker thread —
            # asyncio.wait_for can't actually cancel CPU-bound work handed to
            # asyncio.to_thread, it only stops waiting on it. Retrying would
            # start a second thread competing with the still-running first
            # one for the same CPU instead of replacing it, so a slow host
            # spirals into every future call timing out too. One try, with
            # enough headroom for a busy shared host, beats a retry here.
            timeout_s=self._segment_timeout_s,
            max_retries=0,
            breaker=self._breaker,
        )

    async def health(self) -> bool:
        try:
            await self._ensure_loaded()
            return True
        except Exception:  # noqa: BLE001 — health check must never raise
            return False


# Engine-style name used by the configurable factory, while retaining the
# existing public class for backward compatibility.
FasterWhisperEngine = FasterWhisperSTTProvider
