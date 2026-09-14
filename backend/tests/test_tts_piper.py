from unittest.mock import AsyncMock, patch

from app.core.config import get_settings
from app.providers.tts.piper import PiperTTSProvider


async def test_urdu_uses_espeak_ng_without_loading_a_piper_voice() -> None:
    """Piper ships no Urdu voice — synthesize() must dispatch to espeak-ng for
    `language="ur"` and never attempt to load/download a Piper voice model."""
    provider = PiperTTSProvider(get_settings())

    fake_proc = AsyncMock()
    fake_proc.communicate = AsyncMock(return_value=(b"RIFF...fake-wav-bytes", b""))
    fake_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=fake_proc) as create_exec:
        audio = await provider.synthesize("خوش آمدید", language="ur")

    assert audio == b"RIFF...fake-wav-bytes"
    assert provider._voices == {}  # no Piper voice ever loaded
    args = create_exec.call_args.args
    assert args[0] == "espeak-ng"
    assert "ur" in args
    assert "خوش آمدید" in args


async def test_urdu_espeak_failure_raises() -> None:
    provider = PiperTTSProvider(get_settings())

    fake_proc = AsyncMock()
    fake_proc.communicate = AsyncMock(return_value=(b"", b"voice not found"))
    fake_proc.returncode = 1

    with patch("asyncio.create_subprocess_exec", return_value=fake_proc):
        try:
            await provider.synthesize("test", language="ur")
        except RuntimeError as exc:
            assert "espeak-ng" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")
