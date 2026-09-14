from typing import Protocol


class TTSProvider(Protocol):
    """synthesize returns 16-bit PCM WAV bytes, mono."""

    async def synthesize(self, text: str, *, language: str = "en") -> bytes: ...

    async def health(self) -> bool: ...
