"""Adaptive energy voice activity detection for streamed PCM16 microphone audio."""

import audioop

DEFAULT_SILENCE_RMS_THRESHOLD = 700
DEFAULT_SILENCE_DURATION_MS = 700
DEFAULT_MIN_SPEECH_DURATION_MS = 500
DEFAULT_MAX_UTTERANCE_DURATION_MS = 60_000
BYTES_PER_SAMPLE = 2  # 16-bit PCM, per architecture.md §3


class SimpleVAD:
    def __init__(
        self,
        *,
        silence_rms_threshold: int = DEFAULT_SILENCE_RMS_THRESHOLD,
        silence_duration_ms: int = DEFAULT_SILENCE_DURATION_MS,
        min_speech_duration_ms: int = DEFAULT_MIN_SPEECH_DURATION_MS,
        max_utterance_duration_ms: int = DEFAULT_MAX_UTTERANCE_DURATION_MS,
    ) -> None:
        self._minimum_threshold = silence_rms_threshold
        self._threshold = float(silence_rms_threshold)
        self._silence_duration_ms = silence_duration_ms
        self._min_speech_duration_ms = min_speech_duration_ms
        self._max_utterance_duration_ms = max_utterance_duration_ms
        self._trailing_silence_ms = 0
        self._candidate_speech_ms = 0
        self._utterance_duration_ms = 0
        self._heard_speech = False
        self._noise_floor = 0.0

    @property
    def has_heard_speech(self) -> bool:
        """Whether the current utterance contains audio above the speech threshold."""
        return self._heard_speech

    def feed(self, chunk: bytes, *, chunk_duration_ms: int) -> bool:
        """Feed one audio chunk; returns True once trailing silence has
        crossed the threshold *and* some speech was heard first — a chunk
        stream that's silent from the very start isn't "end of utterance",
        it's "nothing said yet"."""
        if len(chunk) < BYTES_PER_SAMPLE:
            return False

        rms = audioop.rms(chunk, BYTES_PER_SAMPLE)
        speech_was_detected = self._heard_speech

        if not self._heard_speech and rms < self._threshold:
            # Learn the room/device floor while idle. The multiplier prevents
            # fans and steady speaker leakage from becoming candidate speech,
            # while the configured minimum keeps quiet-room behavior stable.
            alpha = 0.12
            self._noise_floor = (
                rms if self._noise_floor == 0 else (1 - alpha) * self._noise_floor + alpha * rms
            )
            self._threshold = max(self._minimum_threshold, self._noise_floor * 4.0)

        if rms < self._threshold:
            self._candidate_speech_ms = 0
            self._trailing_silence_ms += chunk_duration_ms
        else:
            self._candidate_speech_ms += chunk_duration_ms
            if self._candidate_speech_ms >= self._min_speech_duration_ms:
                self._heard_speech = True
            self._trailing_silence_ms = 0

        if speech_was_detected:
            self._utterance_duration_ms += chunk_duration_ms
        elif self._heard_speech:
            self._utterance_duration_ms = self._candidate_speech_ms

        return self._heard_speech and (
            self._trailing_silence_ms >= self._silence_duration_ms
            or self._utterance_duration_ms >= self._max_utterance_duration_ms
        )

    def reset(self) -> None:
        self._trailing_silence_ms = 0
        self._candidate_speech_ms = 0
        self._utterance_duration_ms = 0
        self._heard_speech = False
