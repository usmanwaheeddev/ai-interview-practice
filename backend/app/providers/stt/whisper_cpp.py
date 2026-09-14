"""whisper.cpp CLI adapter using Metal-capable local binaries on macOS."""

import asyncio
import json
import os
import tempfile
import wave
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.providers.resilience import CircuitBreaker, call_with_resilience
from app.providers.stt.base import Transcript
from app.services.audio import STT_SAMPLE_RATE, resample_pcm16_mono

logger = get_logger(__name__)


class WhisperCppEngine:
    """Transcribe PCM16 audio through a compiled whisper.cpp CLI.

    whisper.cpp has an initial prompt but no separate hotwords option, so
    hotwords are appended to ``--prompt``. Upstream owns the shared 10-second
    streaming windows; this adapter handles exactly one window per call.
    """

    def __init__(self, settings: Settings) -> None:
        self._binary = Path(settings.whisper_cpp_binary_path).expanduser()
        self._model = Path(settings.whisper_cpp_model_path).expanduser()
        self._model_size = settings.stt_model_size or self._model.stem
        self._threads = settings.whisper_cpp_threads
        self._breaker = CircuitBreaker()

    def _validate_installation(self) -> None:
        if not self._binary.is_file() or not os.access(self._binary, os.X_OK):
            raise RuntimeError(
                "whisper.cpp binary is missing or not executable: " f"{self._binary}"
            )
        if not self._model.is_file():
            raise RuntimeError(f"whisper.cpp model is missing: {self._model}")

    @staticmethod
    def _write_wav(path: Path, pcm: bytes) -> None:
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(STT_SAMPLE_RATE)
            wav.writeframes(pcm)

    @staticmethod
    def _parse_json(path: Path) -> Transcript:
        try:
            payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            chunks = payload.get("transcription", [])
            text = " ".join(
                str(chunk.get("text", "")).strip()
                for chunk in chunks
                if isinstance(chunk, dict)
            ).strip()
            result = payload.get("result", {})
            language = result.get("language") if isinstance(result, dict) else None
            return Transcript(text=text, language=language if isinstance(language, str) else None)
        except (OSError, ValueError, TypeError) as exc:
            raise RuntimeError("whisper.cpp produced invalid JSON output") from exc

    async def transcribe(
        self,
        audio: bytes,
        *,
        sample_rate: int = 16000,
        language: str | None = None,
        hotwords: str | None = None,
        initial_prompt: str | None = None,
    ) -> Transcript:
        self._validate_installation()
        pcm_16k = resample_pcm16_mono(
            audio, from_rate=sample_rate, to_rate=STT_SAMPLE_RATE
        )

        async def _call() -> Transcript:
            # TemporaryDirectory removes the WAV and whisper.cpp JSON result
            # after every call, including provider failures and cancellation.
            with tempfile.TemporaryDirectory(prefix="hiring-whisper-cpp-") as directory:
                temp_dir = Path(directory)
                wav_path = temp_dir / "segment.wav"
                output_base = temp_dir / "result"
                self._write_wav(wav_path, pcm_16k)

                command = [
                    str(self._binary),
                    "--model",
                    str(self._model),
                    "--file",
                    str(wav_path),
                    "--language",
                    language or "auto",
                    "--threads",
                    str(self._threads),
                    "--output-json",
                    "--output-file",
                    str(output_base),
                    "--no-prints",
                    "--no-timestamps",
                ]
                prompt_parts = [part.strip() for part in (initial_prompt, hotwords) if part]
                if prompt_parts:
                    # No direct hotwords or condition_on_previous_text flags
                    # exist in whisper-cli. The shared caller supplies recent
                    # text, and both forms of context are expressed as prompt.
                    command.extend(["--prompt", " Important terms: ".join(prompt_parts)[:1000]])

                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout, stderr = await process.communicate()
                except asyncio.CancelledError:
                    process.kill()
                    await process.wait()
                    raise
                if process.returncode != 0:
                    detail = (stderr or stdout).decode("utf-8", errors="replace").strip()
                    raise RuntimeError(
                        f"whisper.cpp exited with status {process.returncode}: {detail[-500:]}"
                    )
                return self._parse_json(output_base.with_suffix(".json"))

        logger.debug("whisper_cpp.transcribing", model=self._model_size)
        return await call_with_resilience(
            _call,
            provider="whisper_cpp",
            operation="transcribe",
            timeout_s=30.0,
            max_retries=0,
            breaker=self._breaker,
        )

    async def health(self) -> bool:
        try:
            self._validate_installation()
            return True
        except RuntimeError:
            return False


# Explicit provider-style alias for consistency with the existing class name.
WhisperCppSTTProvider = WhisperCppEngine
