import asyncio
import io
import json
import threading
import wave
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.providers.resilience import CircuitBreaker, call_with_resilience

logger = get_logger(__name__)


_ESPEAK_LANGUAGE = "ur"  # the one spoken language with no Piper voice at all


class PiperTTSProvider:
    """Local, self-hosted, no API key — see memory.md ADR-014. CPU synthesis
    via Piper. Voice models download lazily on first use into a shared volume
    (see docker-compose.yml `piper_voices`), so subsequent container starts
    don't re-download them. One voice is loaded per spoken language that has
    a Piper voice; Urdu has none, so it's synthesized with the espeak-ng
    binary instead (see `_synthesize_espeak`) — robotic, but functional."""

    def __init__(self, settings: Settings) -> None:
        self._voice_names = {"en": settings.piper_voice, "hi": settings.piper_voice_hi}
        self._voices_dir = Path(settings.piper_voices_dir)
        # piper-tts ships no type stubs — PiperVoice resolves to Any.
        self._voices: dict[str, Any] = {}
        self._load_lock = asyncio.Lock()
        self._synthesis_lock = threading.Lock()
        self._breaker = CircuitBreaker()

    async def _ensure_loaded(self, language: str) -> None:
        if language in self._voices:
            return
        async with self._load_lock:
            if language in self._voices:
                return

            voice_name = self._voice_names[language]
            model_path = self._voices_dir / f"{voice_name}.onnx"
            if not model_path.exists():
                logger.info("piper.downloading_voice", voice=voice_name)
                self._voices_dir.mkdir(parents=True, exist_ok=True)
                proc = await asyncio.create_subprocess_exec(
                    "python3",
                    "-m",
                    "piper.download_voices",
                    voice_name,
                    "--download-dir",
                    str(self._voices_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
                if proc.returncode != 0:
                    raise RuntimeError(f"piper voice download failed: {stderr.decode()}")

            logger.info("piper.loading_voice", voice=voice_name)

            def _load() -> Any:
                import onnxruntime
                from piper import PiperVoice
                from piper.config import PiperConfig

                # Default ONNX thread pools oversubscribe Docker Desktop's CPU quota.
                options = onnxruntime.SessionOptions()
                options.intra_op_num_threads = 2
                options.inter_op_num_threads = 1
                options.add_session_config_entry("session.intra_op.allow_spinning", "0")
                return PiperVoice(
                    config=PiperConfig.from_dict(
                        json.loads(Path(f"{model_path}.json").read_text())
                    ),
                    session=onnxruntime.InferenceSession(
                        str(model_path), sess_options=options, providers=["CPUExecutionProvider"]
                    ),
                    download_dir=self._voices_dir,
                )

            self._voices[language] = await asyncio.to_thread(_load)
            logger.info("piper.loaded_voice", voice=voice_name)

    def _synthesize_sync(self, text: str, language: str) -> bytes:
        voice = self._voices[language]
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            # synthesize_wav (not synthesize) — it sets the WAV header
            # (rate/width/channels) from the first audio chunk automatically.
            # `synthesize()` alone returns raw AudioChunks and leaves the
            # caller to configure the wave writer, which is what broke here
            # (see memory.md §6 gotcha on this).
            with self._synthesis_lock:
                voice.synthesize_wav(text, wav_file)
        return buffer.getvalue()

    async def _synthesize_espeak(self, text: str) -> bytes:
        """Urdu has no Piper voice — espeak-ng (apt-installed in the backend
        image) speaks it directly instead, at lower quality than a trained
        Piper voice. `--stdout` writes WAV bytes straight to stdout, so no
        temp file is needed."""
        proc = await asyncio.create_subprocess_exec(
            "espeak-ng",
            "-v",
            _ESPEAK_LANGUAGE,
            "--stdout",
            text,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"espeak-ng synthesis failed: {stderr.decode()}")
        return stdout

    async def synthesize(self, text: str, *, language: str = "en") -> bytes:
        if language == _ESPEAK_LANGUAGE:

            async def _call_espeak() -> bytes:
                return await self._synthesize_espeak(text)

            return await call_with_resilience(
                _call_espeak,
                provider="espeak_ng",
                operation="synthesize",
                timeout_s=30.0,
                max_retries=0,
                breaker=self._breaker,
            )

        await self._ensure_loaded(language)

        async def _call() -> bytes:
            return await asyncio.to_thread(self._synthesize_sync, text, language)

        return await call_with_resilience(
            _call,
            provider="piper",
            operation="synthesize",
            timeout_s=30.0,
            # Retrying a timed-out thread cannot cancel its native inference;
            # avoid queuing duplicate CPU work while the first call finishes.
            max_retries=0,
            breaker=self._breaker,
        )

    async def health(self) -> bool:
        try:
            await self._ensure_loaded("en")
            return True
        except Exception:  # noqa: BLE001 — health check must never raise
            return False
