from app.providers.stt.base import Transcript


class FakeSTTProvider:
    """Returns a fixed transcript regardless of audio content — deterministic
    for tests. See plan.md §3.7. `language` is the language this fake claims
    to have detected (tests use it to simulate the candidate speaking a
    given language for the WS handler's auto-switch)."""

    def __init__(self, language: str = "en") -> None:
        self._language = language

    async def transcribe(
        self,
        audio: bytes,
        *,
        sample_rate: int = 16000,
        language: str | None = None,
        hotwords: str | None = None,
        initial_prompt: str | None = None,
    ) -> Transcript:
        return Transcript(
            text="This is a fake transcript.", confidence=1.0, language=self._language
        )

    async def health(self) -> bool:
        return True
