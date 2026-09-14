import json
import wave
from pathlib import Path

from app.core.config import Settings
from app.providers.stt.whisper_cpp import WhisperCppEngine


class FakeProcess:
    returncode = 0

    async def communicate(self):
        return b"", b""


async def test_transcribes_via_temp_16khz_wav_and_cleans_up(tmp_path, monkeypatch) -> None:
    binary = tmp_path / "whisper-cli"
    binary.write_text("binary", encoding="utf-8")
    binary.chmod(0o755)
    model = tmp_path / "ggml-small.en-q5_0.bin"
    model.write_bytes(b"model")
    settings = Settings(
        stt_provider="faster_whisper",
        stt_engine="whisper_cpp",
        whisper_cpp_binary_path=str(binary),
        whisper_cpp_model_path=str(model),
    )
    engine = WhisperCppEngine(settings)
    observed: dict[str, object] = {}

    async def fake_exec(*command, **kwargs):
        wav_path = Path(command[command.index("--file") + 1])
        output_base = Path(command[command.index("--output-file") + 1])
        with wave.open(str(wav_path), "rb") as wav:
            observed["rate"] = wav.getframerate()
            observed["channels"] = wav.getnchannels()
            observed["width"] = wav.getsampwidth()
        observed["wav_path"] = wav_path
        observed["command"] = command
        output_base.with_suffix(".json").write_text(
            json.dumps(
                {
                    "result": {"language": "en"},
                    "transcription": [{"text": " Hello"}, {"text": " world."}],
                }
            ),
            encoding="utf-8",
        )
        return FakeProcess()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    transcript = await engine.transcribe(
        b"\x00\x00" * 800,
        sample_rate=8000,
        language="en",
        hotwords="Mubashir Shaheen, FastAPI",
        initial_prompt="Previous transcript: I use Python",
    )

    assert transcript.text == "Hello world."
    assert transcript.language == "en"
    assert observed == {
        **observed,
        "rate": 16000,
        "channels": 1,
        "width": 2,
    }
    command = observed["command"]
    assert "--prompt" in command
    assert "Mubashir Shaheen" in command[command.index("--prompt") + 1]
    assert not observed["wav_path"].exists()


async def test_health_is_false_without_binary_or_model(tmp_path) -> None:
    engine = WhisperCppEngine(
        Settings(
            whisper_cpp_binary_path=str(tmp_path / "missing-cli"),
            whisper_cpp_model_path=str(tmp_path / "missing-model.bin"),
        )
    )
    assert await engine.health() is False
