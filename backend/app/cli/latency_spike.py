"""Interview turn latency spike — phases.md Phase 2, the go/no-go gate.

Measures end-of-speech -> first-agent-audio latency for a full STT -> LLM ->
TTS turn against whatever providers are configured (LLM_PROVIDER, STT_PROVIDER,
TTS_PROVIDER in .env). Run via `make interview-cli`.

Scope note: VAD (end-of-utterance detection) isn't measured here — it needs a
live audio stream, which doesn't exist until Phase 3/4. Per plan.md §5's stage
budget, VAD is ~300ms and adds to whatever this harness reports. TTS latency
here is total synthesis time, not true streaming first-byte time (the
TTSProvider interface returns a complete WAV) — a conservative (worse) proxy,
since real streaming in Phase 4 will only improve on this number.
"""

import argparse
import asyncio
import io
import time
import wave

import numpy as np

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.providers.llm import get_llm_provider
from app.providers.stt import get_stt_provider
from app.providers.tts import get_tts_provider

logger = get_logger(__name__)

TARGET_P50_MS = 1500
TARGET_P95_MS = 2500

# Synthesized via TTS to build self-contained fixture audio — no external
# recordings needed. Phrased like real interview answers so the LLM stage
# gets a representative prompt, not lorem ipsum.
CANDIDATE_ANSWERS = [
    "I led the rebuild of our payments service, and the hardest part was "
    "making retries idempotent under concurrent writes.",
    "When a deploy broke production, I rolled back within five minutes and "
    "wrote a postmortem the same day.",
    "I mostly communicate through short written design docs, then a quick "
    "sync to align on tradeoffs before writing code.",
    "I once disagreed with my manager's approach and pushed back with data "
    "from a load test, which changed the plan.",
    "My biggest failure was underestimating a migration's scope, and I "
    "learned to timebox spikes before committing to a deadline.",
]

DIRECTOR_SYSTEM_PROMPT = (
    "You are conducting a structured job interview. Given the candidate's last "
    "answer, respond with exactly one short follow-up question, under 25 words. "
    "Do not repeat the question. Do not add commentary."
)


def _wav_to_pcm_native(wav_bytes: bytes) -> tuple[bytes, int]:
    """Extract raw PCM + its native sample rate — deliberately *not*
    resampled here. Resampling to what STT needs happens inside the timed
    `stt.transcribe()` call (see FasterWhisperSTTProvider), so this harness
    measures the real cost including that step, the way a live pipeline
    would incur it."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        return wf.readframes(wf.getnframes()), wf.getframerate()


def _pct(data: list[float], p: float) -> float:
    return float(np.percentile(np.array(data), p * 100))


async def run_spike(turns: int) -> bool:
    settings = get_settings()
    llm = get_llm_provider()
    stt = get_stt_provider()
    tts = get_tts_provider()

    print(
        f"Providers: LLM={settings.llm_provider} STT={settings.stt_provider} "
        f"TTS={settings.tts_provider}"
    )
    print("Warming up (model load — not counted in per-turn latency)...")
    t0 = time.monotonic()
    llm_ok, stt_ok, tts_ok = await asyncio.gather(llm.health(), stt.health(), tts.health())
    elapsed = time.monotonic() - t0
    print(f"  health check took {elapsed:.1f}s — llm={llm_ok} stt={stt_ok} tts={tts_ok}")
    if not (llm_ok and stt_ok and tts_ok):
        print("A provider failed its health check — aborting.")
        return False

    # health() on Ollama only hits /api/tags — it doesn't load weights into
    # memory. The model only actually loads on its first real inference call,
    # which would otherwise land inside turn 1's measured latency and wreck
    # the stats with a one-off cold-start cost. Force that cost out here.
    t0 = time.monotonic()
    await llm.complete(system="Reply with one word.", user="ping")
    print(f"  llm first-inference load took {time.monotonic() - t0:.1f}s")

    print("Building fixture audio from candidate-answer text via TTS...")
    fixtures: list[tuple[str, bytes, int]] = []
    for text in CANDIDATE_ANSWERS:
        wav_bytes = await tts.synthesize(text)
        pcm, rate = _wav_to_pcm_native(wav_bytes)
        fixtures.append((text, pcm, rate))

    picks = [fixtures[i % len(fixtures)] for i in range(max(turns, 1))]

    stt_ms_all: list[float] = []
    llm_ms_all: list[float] = []
    tts_ms_all: list[float] = []
    total_ms_all: list[float] = []

    for i, (source_text, pcm, rate) in enumerate(picks):
        t_turn = time.monotonic()

        t0 = time.monotonic()
        transcript = await stt.transcribe(pcm, sample_rate=rate)
        stt_ms = (time.monotonic() - t0) * 1000

        t0 = time.monotonic()
        response = await llm.complete(system=DIRECTOR_SYSTEM_PROMPT, user=transcript.text)
        llm_ms = (time.monotonic() - t0) * 1000

        t0 = time.monotonic()
        await tts.synthesize(response)
        tts_ms = (time.monotonic() - t0) * 1000

        total_ms = (time.monotonic() - t_turn) * 1000

        stt_ms_all.append(stt_ms)
        llm_ms_all.append(llm_ms)
        tts_ms_all.append(tts_ms)
        total_ms_all.append(total_ms)

        print(
            f"turn {i + 1}/{len(picks)}: stt={stt_ms:5.0f}ms llm={llm_ms:5.0f}ms "
            f"tts={tts_ms:5.0f}ms total={total_ms:5.0f}ms"
        )
        print(f"   source : {source_text[:70]!r}")
        print(f"   heard  : {transcript.text[:70]!r}")
        print(f"   agent  : {response[:70]!r}")

    print()
    print("=== Latency summary (ms) — VAD not included, see module docstring ===")
    for name, data in [
        ("STT", stt_ms_all),
        ("LLM", llm_ms_all),
        ("TTS", tts_ms_all),
        ("TOTAL", total_ms_all),
    ]:
        print(
            f"{name:6} p50={_pct(data, 0.5):7.0f}  p95={_pct(data, 0.95):7.0f}  "
            f"min={min(data):7.0f}  max={max(data):7.0f}"
        )

    p50_total, p95_total = _pct(total_ms_all, 0.5), _pct(total_ms_all, 0.95)
    gate_pass = p50_total <= TARGET_P50_MS and p95_total <= TARGET_P95_MS

    verdict = "PASS" if gate_pass else "FAIL"
    print()
    print(f"Gate: p50 <= {TARGET_P50_MS}ms and p95 <= {TARGET_P95_MS}ms (plan.md §5)")
    print(f"Result: p50={p50_total:.0f}ms p95={p95_total:.0f}ms -> {verdict}")
    return gate_pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Interview turn latency spike (phases.md Phase 2)")
    parser.add_argument("--turns", type=int, default=10)
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.debug)

    passed = asyncio.run(run_spike(args.turns))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
