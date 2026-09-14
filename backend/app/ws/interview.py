"""Real-time voice transport for directly owned mock interviews."""

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import APIRouter, Cookie, Depends, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.queue import get_queue
from app.core.redis import get_redis
from app.core.security import TokenType, decode_token
from app.db.models import (
    MockInterview,
    MockInterviewState,
    MockInterviewTurn,
    Resume,
    SpokenLanguage,
    User,
)
from app.db.session import get_db
from app.providers.llm import get_llm_provider
from app.providers.resilience import CircuitOpenError
from app.providers.stt import get_stt_provider
from app.providers.tts import get_tts_provider
from app.services.interview.director import Director
from app.services.interview.engine import InterviewEngine, TurnKind
from app.services.interview.memory import load_user_memory
from app.services.interview.plan import InterviewPlan
from app.services.interview.state_store import load_state, save_state
from app.services.interview.streaming_stt import is_plausible_transcript, merge_transcript_text
from app.services.interview.vad import SimpleVAD
from app.services.interview.whisper_context import (
    build_whisper_hotwords,
    build_whisper_initial_prompt,
)

# How long the candidate must be silent before their answer is treated as
# finished and sent for transcription.
ANSWER_SILENCE_DURATION_MS = 3_000
TRANSCRIPTION_SEGMENT_DURATION_S = 20
TRANSCRIPTION_OVERLAP_DURATION_MS = 250
MIN_TRANSCRIPTION_WAIT_S = 45
MAX_TRANSCRIPTION_WAIT_S = 120
TRANSCRIPTION_WAIT_PER_SEGMENT_S = 25

router = APIRouter()
logger = get_logger(__name__)


async def wait_for_session_end(websocket: WebSocket) -> None:
    """Wait for an end command while ignoring stale microphone frames.

    A few binary frames may already be in flight when an agent turn begins.
    They are not control messages and must never be interpreted as a TTS
    failure or interruption.
    """
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect()
        text = message.get("text")
        if not text:
            continue
        data = json.loads(text)
        if data.get("type") == "session.end":
            return


@router.websocket("/ws/mock-interviews/{interview_id}")
async def interview_ws(
    websocket: WebSocket,
    interview_id: uuid.UUID,
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    interview = await db.get(MockInterview, interview_id)
    try:
        payload = decode_token(access_token or "", expected_type=TokenType.ACCESS)
        if (
            interview is None
            or str(interview.user_id) != payload["sub"]
            or await db.get(User, interview.user_id) is None
        ):
            raise ValueError("Not owner")
    except Exception:
        await websocket.close(code=1008)
        return
    if interview.consent_at is None:
        await websocket.close(code=4001)
        return
    if interview.state not in (
        MockInterviewState.READY,
        MockInterviewState.IN_PROGRESS,
        MockInterviewState.DISCONNECTED,
    ):
        await websocket.close(code=1008)
        return
    lock = f"mock-interview:connection:{interview.id}"
    lock_value = str(uuid.uuid4())
    if not await redis.set(lock, lock_value, nx=True, ex=interview.duration_minutes * 60 + 120):
        await websocket.close(code=4009)
        return
    await websocket.accept()
    # Live interviews are English-only. Keep the persisted value normalized
    # as well so resumed sessions and reports cannot switch language.
    interview.spoken_language = SpokenLanguage.EN
    user = await db.get(User, interview.user_id)
    resume = await db.get(Resume, interview.resume_id) if interview.resume_id else None
    # Only AI-extracted structured resume fields are used as vocabulary hints.
    whisper_hotwords = build_whisper_hotwords(
        user.full_name if user else "",
        resume.parsed if resume and isinstance(resume.parsed, dict) else {},
        interview.job_description or "",
    )
    memory_context = await load_user_memory(
        db, interview.user_id, exclude_interview_id=interview.id
    )
    engine = InterviewEngine(
        InterviewPlan.model_validate(interview.interview_plan),
        Director(
            get_llm_provider(),
            provider_name=get_settings().llm_provider,
            spoken_language="en",
            memory_context=memory_context,
        ),
        state=await load_state(redis, interview.id),
        spoken_language="en",
    )
    stt, tts = get_stt_provider(), get_tts_provider()
    next_index = await db.scalar(
        select(MockInterviewTurn.turn_index)
        .where(MockInterviewTurn.interview_id == interview.id)
        .order_by(MockInterviewTurn.turn_index.desc())
        .limit(1)
    )
    turn_index = 0 if next_index is None else next_index + 1
    done = False
    transcription_worker: asyncio.Task[None] | None = None
    # This session's own running transcript, fed back into the Director so a
    # follow-up can reference something the candidate said earlier turn to
    # turn — not just the immediately preceding answer. Reloaded from
    # Postgres on reconnect so a resumed session still has its own history.
    session_transcript: list[str] = [
        f"{'Interviewer' if turn.speaker == 'agent' else 'Candidate'}: {turn.text}"
        for turn in (
            await db.scalars(
                select(MockInterviewTurn)
                .where(MockInterviewTurn.interview_id == interview.id)
                .order_by(MockInterviewTurn.turn_index)
            )
        ).all()
    ]

    def elapsed():
        start = interview.started_at
        if start is None:
            return 0
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        return min(
            interview.duration_minutes * 60,
            max(0, int((datetime.now(UTC) - start).total_seconds())),
        )

    async def tick():
        interview.elapsed_s = elapsed()
        engine.state.elapsed_s = interview.elapsed_s
        await db.commit()
        await websocket.send_json(
            dict(type="timer.tick", elapsed_s=interview.elapsed_s, remaining_s=engine.remaining_s)
        )

    async def record(speaker, text):
        nonlocal turn_index
        now = datetime.now(UTC)
        db.add(
            MockInterviewTurn(
                interview_id=interview.id,
                turn_index=turn_index,
                speaker=speaker,
                text=text,
                started_at=now,
                ended_at=now,
            )
        )
        turn_index += 1
        session_transcript.append(f"{'Interviewer' if speaker == 'agent' else 'Candidate'}: {text}")
        await db.commit()

    async def speak(utterance) -> bool:
        await record("agent", utterance.text)
        await websocket.send_json(
            dict(
                type="agent.speaking_start",
                turn_id=turn_index - 1,
                text=utterance.text,
                question_source=utterance.question_source,
                language="en",
            )
        )
        synthesis = asyncio.create_task(tts.synthesize(utterance.text, language="en"))
        control = asyncio.create_task(wait_for_session_end(websocket))
        try:
            completed, _ = await asyncio.wait(
                {synthesis, control},
                timeout=max(1, min(45, engine.remaining_s)),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if control in completed:
                control.result()
                synthesis.cancel()
                await asyncio.gather(synthesis, return_exceptions=True)
                await websocket.send_json(
                    dict(type="agent.speaking_end", turn_id=turn_index - 1)
                )
                return True
            if synthesis not in completed:
                raise TimeoutError
            await websocket.send_bytes(synthesis.result())
        except WebSocketDisconnect:
            raise
        except Exception:
            await websocket.send_json(
                dict(
                    type="error",
                    code="voice_unavailable",
                    message="Voice playback unavailable. Read the question shown here.",
                    recoverable=True,
                )
            )
        finally:
            if not synthesis.done():
                synthesis.cancel()
                await asyncio.gather(synthesis, return_exceptions=True)
            control.cancel()
            await asyncio.gather(control, return_exceptions=True)
        await websocket.send_json(dict(type="agent.speaking_end", turn_id=turn_index - 1))
        return False

    async def finish():
        nonlocal done
        interview.elapsed_s = elapsed()
        interview.ended_at = datetime.now(UTC)
        interview.state = MockInterviewState.SCORING
        engine.state.complete = True
        await save_state(redis, interview.id, engine.state)
        await db.commit()
        done = True
        try:
            queue = await get_queue()
            await queue.enqueue_job("score_mock_interview", str(interview.id))
        except Exception:
            interview.state = MockInterviewState.COMPLETED
            interview.failure_reason = "Report queue unavailable. Retry from the report page."
            await db.commit()
        await websocket.send_json(dict(type="session.complete", reason="completed"))

    try:
        start_data = await asyncio.wait_for(websocket.receive_json(), timeout=20)
        if start_data.get("type") != "session.start":
            await websocket.close(code=1008)
            return
        sample_rate = int(start_data.get("sample_rate", 16000))
        if sample_rate not in (16000, 22050, 24000, 44100, 48000):
            await websocket.close(code=1008)
            return
        interview.started_at = interview.started_at or datetime.now(UTC)
        interview.state = MockInterviewState.IN_PROGRESS
        await db.commit()
        await tick()
        if turn_index == 0:
            if await speak(engine.start()):
                await finish()
                return
        vad, buffer = SimpleVAD(silence_duration_ms=ANSWER_SILENCE_DURATION_MS), bytearray()
        pre_speech_buffer = bytearray()
        pre_speech_bytes = sample_rate * 2  # retain one second so opening words are not lost
        segment_bytes = sample_rate * 2 * TRANSCRIPTION_SEGMENT_DURATION_S
        overlap_bytes = sample_rate * 2 * TRANSCRIPTION_OVERLAP_DURATION_MS // 1000
        segment_queue: asyncio.Queue[tuple[int, int, bytes] | None] = asyncio.Queue()
        segment_results: dict[int, dict[int, Any]] = {}
        segment_errors: dict[int, list[Exception]] = {}
        partial_texts: dict[int, str] = {}
        abandoned_generations: set[int] = set()
        active_generation = 0

        async def transcribe_segments() -> None:
            while True:
                item = await segment_queue.get()
                try:
                    if item is None:
                        return
                    generation, index, audio = item
                    current_question = session_transcript[-1] if session_transcript else ""
                    turn_hotwords = build_whisper_hotwords(
                        user.full_name if user else "",
                        resume.parsed if resume and isinstance(resume.parsed, dict) else {},
                        interview.job_description or "",
                        current_question,
                    )
                    result = await stt.transcribe(
                        audio,
                        sample_rate=sample_rate,
                        language="en",
                        hotwords=turn_hotwords or whisper_hotwords or None,
                        initial_prompt=build_whisper_initial_prompt(
                            turn_hotwords or whisper_hotwords,
                            partial_texts.get(generation, ""),
                        ),
                    )
                    if generation in abandoned_generations:
                        continue
                    generation_results = segment_results.setdefault(generation, {})
                    generation_results[index] = result
                    partial_text = merge_transcript_text(
                        partial_texts.get(generation, ""), result.text
                    )
                    partial_texts[generation] = partial_text
                    if generation == active_generation and partial_text:
                        await websocket.send_json(
                            dict(
                                type="transcript.partial",
                                turn_id=turn_index,
                                text=partial_text,
                                language="en",
                            )
                        )
                except Exception as exc:
                    if item is not None and item[0] not in abandoned_generations:
                        segment_errors.setdefault(item[0], []).append(exc)
                finally:
                    segment_queue.task_done()

        transcription_worker = asyncio.create_task(transcribe_segments())
        next_segment_index = 0
        while not done:
            await tick()
            if engine.remaining_s <= 0:
                await finish()
                break
            try:
                message = await asyncio.wait_for(
                    websocket.receive(), timeout=min(5, engine.remaining_s)
                )
            except TimeoutError:
                continue
            if message["type"] == "websocket.disconnect":
                raise WebSocketDisconnect()
            if message.get("text"):
                data = json.loads(message["text"])
                if data.get("type") == "session.end":
                    await finish()
                    break
                continue
            chunk = message.get("bytes") or b""
            if len(chunk) % 2 or len(chunk) > 192000:
                await websocket.close(code=1008)
                break
            speech_was_detected = vad.has_heard_speech
            utterance_complete = vad.feed(
                chunk, chunk_duration_ms=len(chunk) * 1000 // (sample_rate * 2)
            )
            # Do not send the candidate's thinking-time silence to Whisper.
            # Keeping it made later answers progressively expensive when the
            # candidate paused before speaking and caused avoidable timeouts.
            if vad.has_heard_speech:
                if not speech_was_detected:
                    buffer.extend(pre_speech_buffer)
                    pre_speech_buffer.clear()
                buffer.extend(chunk)
            else:
                pre_speech_buffer.extend(chunk)
                if len(pre_speech_buffer) > pre_speech_bytes:
                    del pre_speech_buffer[:-pre_speech_bytes]
            while len(buffer) >= segment_bytes:
                segment_queue.put_nowait(
                    (active_generation, next_segment_index, bytes(buffer[:segment_bytes]))
                )
                next_segment_index += 1
                del buffer[: segment_bytes - overlap_bytes]
            if not utterance_complete:
                continue
            if buffer and (next_segment_index == 0 or len(buffer) > overlap_bytes):
                segment_queue.put_nowait((active_generation, next_segment_index, bytes(buffer)))
                next_segment_index += 1
            buffer.clear()
            pre_speech_buffer.clear()
            vad.reset()
            # Stop the client sending more microphone frames while this
            # answer is transcribed and evaluated. WebSocket frames received
            # during these provider calls would otherwise queue up and be
            # mistaken for the candidate's next answer.
            await websocket.send_json(dict(type="candidate.processing"))
            generation = active_generation
            answer_timeout_s = min(
                MAX_TRANSCRIPTION_WAIT_S,
                max(
                    MIN_TRANSCRIPTION_WAIT_S,
                    next_segment_index * TRANSCRIPTION_WAIT_PER_SEGMENT_S,
                ),
                engine.remaining_s,
            )
            try:
                await asyncio.wait_for(
                    segment_queue.join(), timeout=max(1, answer_timeout_s)
                )
                if segment_errors.get(generation):
                    raise segment_errors[generation][0]
                transcript_text = ""
                generation_results = segment_results.get(generation, {})
                for index in sorted(generation_results):
                    result = generation_results[index]
                    transcript_text = merge_transcript_text(transcript_text, result.text)
                if not transcript_text.strip() or not is_plausible_transcript(transcript_text):
                    await websocket.send_json(
                        dict(
                            type="error",
                            code="no_speech_detected",
                            message="I couldn't transcribe that. Please try your answer again.",
                            recoverable=True,
                        )
                    )
                    continue
                await record("user", transcript_text)
                await websocket.send_json(
                    dict(
                        type="transcript.final",
                        turn_id=turn_index - 1,
                        text=transcript_text,
                        language="en",
                    )
                )
                utterance = await asyncio.wait_for(
                    engine.submit_candidate_answer(
                        transcript_text,
                        elapsed_s=elapsed(),
                        session_history="\n".join(session_transcript[:-1]),
                    ),
                    timeout=max(1, min(45, engine.remaining_s)),
                )
                await save_state(redis, interview.id, engine.state)
                if await speak(utterance):
                    await finish()
                    break
                if utterance.kind == TurnKind.CLOSING:
                    await finish()
            except (TimeoutError, CircuitOpenError):
                abandoned_generations.add(generation)
                # At this point no newer answer can have been queued because
                # the client is in candidate.processing. Discard pending
                # segments from this failed answer; an already-running native
                # call is isolated by FasterWhisper's single-worker executor.
                while True:
                    try:
                        pending = segment_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    if pending is None:
                        segment_queue.put_nowait(None)
                        segment_queue.task_done()
                        break
                    segment_queue.task_done()
                # A provider timeout or an open circuit breaker (repeated
                # recent failures) is transient — surface it as a recoverable
                # in-session error and keep the connection open rather than
                # letting it fall through to the generic handler below, which
                # would end the session on what the candidate could just retry.
                if elapsed() >= interview.duration_minutes * 60:
                    await finish()
                else:
                    await websocket.send_json(
                        dict(
                            type="error",
                            code="provider_timeout",
                            message="Processing timed out. Please repeat your answer.",
                            recoverable=True,
                        )
                    )
            finally:
                segment_results.pop(generation, None)
                segment_errors.pop(generation, None)
                partial_texts.pop(generation, None)
                next_segment_index = 0
                active_generation += 1
        segment_queue.put_nowait(None)
        await transcription_worker
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("mock_interview.connection_failed", interview_id=str(interview.id))
    finally:
        if transcription_worker is not None and not transcription_worker.done():
            transcription_worker.cancel()
            await asyncio.gather(transcription_worker, return_exceptions=True)
        if not done and interview.started_at:
            interview.elapsed_s = elapsed()
            interview.state = MockInterviewState.DISCONNECTED
            await save_state(redis, interview.id, engine.state)
            await db.commit()
        await cast(Any, redis).eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] "
            "then return redis.call('del', KEYS[1]) else return 0 end",
            1,
            lock,
            lock_value,
        )
