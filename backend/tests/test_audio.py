import io
import struct
import wave

from app.services.audio import resample_pcm16_mono, wav_bytes_to_pcm16


def _make_wav(*, n_samples: int, rate: int, channels: int = 1, width: int = 2) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(width)
        wf.setframerate(rate)
        frame = struct.pack("<h", 1000) * channels
        wf.writeframes(frame * n_samples)
    return buffer.getvalue()


def test_resample_noop_when_rate_matches() -> None:
    pcm = struct.pack("<h", 500) * 100
    assert resample_pcm16_mono(pcm, from_rate=16000, to_rate=16000) == pcm


def test_resample_changes_sample_count_proportionally() -> None:
    pcm = struct.pack("<h", 500) * 22050  # 1 second at 22050 Hz
    resampled = resample_pcm16_mono(pcm, from_rate=22050, to_rate=16000)
    n_samples_out = len(resampled) // 2
    # Allow a little slack for resampler edge behaviour.
    assert abs(n_samples_out - 16000) < 50


def test_wav_bytes_to_pcm16_mono_passthrough() -> None:
    wav_bytes = _make_wav(n_samples=16000, rate=16000, channels=1)
    pcm = wav_bytes_to_pcm16(wav_bytes, to_rate=16000)
    assert len(pcm) == 16000 * 2  # 16-bit mono, 1 second


def test_wav_bytes_to_pcm16_downmixes_stereo() -> None:
    wav_bytes = _make_wav(n_samples=8000, rate=16000, channels=2)
    pcm = wav_bytes_to_pcm16(wav_bytes, to_rate=16000)
    assert len(pcm) == 8000 * 2  # mono after downmix


def test_wav_bytes_to_pcm16_resamples_to_target_rate() -> None:
    wav_bytes = _make_wav(n_samples=22050, rate=22050, channels=1)
    pcm = wav_bytes_to_pcm16(wav_bytes, to_rate=16000)
    n_samples_out = len(pcm) // 2
    assert abs(n_samples_out - 16000) < 50
