import struct


def _silent_wav(duration_s: float = 0.1, sample_rate: int = 16000) -> bytes:
    n_samples = int(duration_s * sample_rate)
    data = b"\x00\x00" * n_samples
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(data),
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        sample_rate * 2,
        2,
        16,
        b"data",
        len(data),
    )
    return header + data


class FakeTTSProvider:
    """Returns a short silent WAV regardless of input text — deterministic
    for tests. See plan.md §3.7."""

    async def synthesize(self, text: str, *, language: str = "en") -> bytes:
        return _silent_wav()

    async def health(self) -> bool:
        return True
