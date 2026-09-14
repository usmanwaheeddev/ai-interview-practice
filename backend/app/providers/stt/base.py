from dataclasses import dataclass
from typing import Protocol


@dataclass
class Transcript:
    text: str
    confidence: float | None = None
    # The language actually detected in the audio, when the provider was
    # asked to auto-detect (see `transcribe`'s `language=None`). None when
    # the provider doesn't support detection or a language was forced.
    language: str | None = None


class STTProvider(Protocol):
    async def transcribe(
        self,
        audio: bytes,
        *,
        sample_rate: int = 16000,
        language: str | None = None,
        hotwords: str | None = None,
        initial_prompt: str | None = None,
    ) -> Transcript: ...

    async def health(self) -> bool: ...
