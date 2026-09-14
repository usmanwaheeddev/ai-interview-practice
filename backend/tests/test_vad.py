import struct

from app.services.interview.vad import SimpleVAD


def _silence_chunk(n_samples: int = 100) -> bytes:
    return struct.pack(f"<{n_samples}h", *([0] * n_samples))


def _loud_chunk(n_samples: int = 100, amplitude: int = 20000) -> bytes:
    return struct.pack(f"<{n_samples}h", *([amplitude, -amplitude] * (n_samples // 2)))


def test_pure_silence_never_triggers_end_of_utterance() -> None:
    vad = SimpleVAD(silence_duration_ms=500, min_speech_duration_ms=250)
    for _ in range(10):
        assert not vad.feed(_silence_chunk(), chunk_duration_ms=250)
        assert not vad.has_heard_speech


def test_speech_then_silence_triggers_after_threshold() -> None:
    vad = SimpleVAD(silence_duration_ms=500, min_speech_duration_ms=250)
    assert not vad.feed(_loud_chunk(), chunk_duration_ms=250)  # speech
    assert not vad.feed(_silence_chunk(), chunk_duration_ms=250)  # 250ms silence
    assert vad.feed(_silence_chunk(), chunk_duration_ms=250)  # 500ms silence -> trigger


def test_speech_resets_silence_counter() -> None:
    vad = SimpleVAD(silence_duration_ms=500, min_speech_duration_ms=250)
    vad.feed(_loud_chunk(), chunk_duration_ms=250)
    vad.feed(_silence_chunk(), chunk_duration_ms=250)
    vad.feed(_loud_chunk(), chunk_duration_ms=250)  # speech again -> resets
    assert not vad.feed(_silence_chunk(), chunk_duration_ms=250)


def test_reset_clears_state() -> None:
    vad = SimpleVAD(silence_duration_ms=500)
    vad.feed(_loud_chunk(), chunk_duration_ms=250)
    vad.feed(_silence_chunk(), chunk_duration_ms=250)
    vad.reset()
    assert not vad.has_heard_speech
    assert not vad.feed(_silence_chunk(), chunk_duration_ms=250)


def test_tiny_chunk_ignored() -> None:
    vad = SimpleVAD(silence_duration_ms=500)
    assert not vad.feed(b"\x00", chunk_duration_ms=250)


def test_single_noise_spike_is_not_treated_as_speech() -> None:
    vad = SimpleVAD(min_speech_duration_ms=500)
    assert not vad.feed(_loud_chunk(), chunk_duration_ms=250)
    assert not vad.has_heard_speech
    assert not vad.feed(_silence_chunk(), chunk_duration_ms=1000)


def test_maximum_utterance_duration_forces_a_boundary() -> None:
    vad = SimpleVAD(
        min_speech_duration_ms=250,
        max_utterance_duration_ms=750,
        silence_duration_ms=5_000,
    )
    assert not vad.feed(_loud_chunk(), chunk_duration_ms=250)
    assert not vad.feed(_loud_chunk(), chunk_duration_ms=250)
    assert vad.feed(_loud_chunk(), chunk_duration_ms=250)
