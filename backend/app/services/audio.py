"""Shared raw-PCM audio utilities. No I/O, no provider dependencies — pure
functions so both provider adapters and the latency-spike CLI use identical,
independently-tested resampling logic rather than each reimplementing it.
"""

import audioop
import io
import wave

STT_SAMPLE_RATE = 16000


def resample_pcm16_mono(pcm: bytes, *, from_rate: int, to_rate: int = STT_SAMPLE_RATE) -> bytes:
    """16-bit signed PCM, already mono. audioop (stdlib) does a fine job for
    speech — no need for a heavier resampling dependency at this quality bar."""
    if from_rate == to_rate:
        return pcm
    resampled, _ = audioop.ratecv(pcm, 2, 1, from_rate, to_rate, None)
    return resampled


def wav_bytes_to_pcm16(wav_bytes: bytes, *, to_rate: int = STT_SAMPLE_RATE) -> bytes:
    """Parse a WAV container down to mono 16-bit PCM at `to_rate`, regardless
    of the WAV's original channel count, sample width or rate."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        channels, width, rate = wf.getnchannels(), wf.getsampwidth(), wf.getframerate()
        pcm = wf.readframes(wf.getnframes())

    if channels > 1:
        pcm = audioop.tomono(pcm, width, 0.5, 0.5)
    if width != 2:
        pcm = audioop.lin2lin(pcm, width, 2)

    return resample_pcm16_mono(pcm, from_rate=rate, to_rate=to_rate)
