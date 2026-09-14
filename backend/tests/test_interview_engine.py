from decimal import Decimal

from app.providers.llm.fake import FakeLLMProvider
from app.services.interview.director import Director
from app.services.interview.engine import (
    CLOSING,
    EngineState,
    InterviewEngine,
    TurnKind,
)
from app.services.interview.plan import InterviewPlan, TopicProbe


def _plan(n: int = 3, time_budget_s: int = 100) -> InterviewPlan:
    return InterviewPlan(
        topics=[
            TopicProbe(
                id=f"comp-{i}",
                label=f"Topic {i}",
                weight=Decimal("1") / Decimal(n),
                time_budget_s=time_budget_s,
                primary_question=f"Question for topic {i}?",
                follow_up_hints=["detail one", "detail two"],
            )
            for i in range(n)
        ]
    )


def _engine(n: int = 3, time_budget_s: int = 100) -> InterviewEngine:
    return InterviewEngine(
        _plan(n, time_budget_s), Director(FakeLLMProvider(), provider_name="fake")
    )


async def test_start_asks_self_introduction() -> None:
    engine = _engine()
    utterance = engine.start()
    assert utterance.kind == TurnKind.SELF_INTRO
    assert utterance.topic_id is None


async def test_self_intro_answer_leads_to_first_topic_question() -> None:
    engine = _engine()
    engine.start()
    utterance = await engine.submit_candidate_answer("I'm a backend engineer.", elapsed_s=5)
    assert utterance.kind == TurnKind.PRIMARY_QUESTION
    assert "Question for topic 0?" in utterance.text
    assert utterance.topic_id == "comp-0"
    assert utterance.question_source == "groq"


async def test_full_interview_covers_every_topic() -> None:
    engine = _engine(n=3, time_budget_s=1000)  # generous budget, never forces advance on time
    engine.start()

    asked_topics: set[str] = set()
    elapsed = 5
    utterance = await engine.submit_candidate_answer("Self introduction.", elapsed_s=elapsed)
    asked_topics.add(utterance.topic_id)  # comp-0, asked right after the self-intro
    for _ in range(50):  # generous cap on turns to avoid an infinite loop on a bug
        elapsed += 10
        utterance = await engine.submit_candidate_answer(
            "A reasonably detailed answer.", elapsed_s=elapsed
        )
        if utterance.topic_id:
            asked_topics.add(utterance.topic_id)
        if engine.is_complete:
            break

    assert engine.is_complete
    assert utterance is not None
    assert utterance.kind == TurnKind.CLOSING
    assert asked_topics == {"comp-0", "comp-1", "comp-2"}


async def test_fake_director_gives_exactly_one_follow_up_per_topic() -> None:
    engine = _engine(n=1, time_budget_s=1000)
    engine.start()
    await engine.submit_candidate_answer("Self introduction.", elapsed_s=5)  # -> comp-0 question

    first = await engine.submit_candidate_answer("thin answer", elapsed_s=10)
    assert first.kind == TurnKind.FOLLOW_UP

    second = await engine.submit_candidate_answer("more detail", elapsed_s=20)
    # only one topic -> after advancing, engine moves to candidate questions
    assert second.kind == TurnKind.CANDIDATE_QUESTIONS


async def test_repeated_clarify_is_capped_like_follow_up() -> None:
    """Regression test — found running interview-sim against a real LLM: a
    model favouring 'clarify' over 'follow_up' looped on one topic
    until the *time* budget eventually saved it, since CLARIFY didn't
    originally count against the same per-topic cap. See memory.md."""

    class AlwaysClarifyProvider(FakeLLMProvider):
        async def extract_json(self, *, prompt: str, text: str) -> dict:
            return {"action": "clarify", "text": "Could you say that again?"}

    engine = InterviewEngine(_plan(n=2, time_budget_s=1000), Director(AlwaysClarifyProvider()))
    engine.start()
    await engine.submit_candidate_answer("Self introduction.", elapsed_s=5)  # -> comp-0 question

    first = await engine.submit_candidate_answer("mumble", elapsed_s=10)
    assert first.kind == TurnKind.CLARIFY

    second = await engine.submit_candidate_answer("mumble again", elapsed_s=20)
    assert second.kind == TurnKind.CLARIFY

    # Third consecutive clarify hits the cap (max 2 extra turns) and is
    # forced to advance without ever consulting the LLM again.
    third = await engine.submit_candidate_answer("mumble a third time", elapsed_s=30)
    assert third.topic_id == "comp-1"


async def test_time_cap_forces_close_regardless_of_director() -> None:
    engine = _engine(n=5, time_budget_s=1000)  # plenty of per-topic budget left
    engine.start()

    utterance = await engine.submit_candidate_answer("answer", elapsed_s=900)  # >= 15:00
    assert utterance.kind == TurnKind.CLOSING
    assert utterance.text == CLOSING
    assert engine.is_complete


async def test_hard_close_window_forces_close_before_full_time_cap() -> None:
    engine = _engine(n=5, time_budget_s=1000)
    engine.start()

    utterance = await engine.submit_candidate_answer("answer", elapsed_s=13 * 60 + 30)
    assert utterance.kind == TurnKind.CLOSING
    assert engine.is_complete


async def test_topic_time_budget_forces_advance() -> None:
    engine = _engine(n=2, time_budget_s=30)
    engine.start()
    await engine.submit_candidate_answer("Self introduction.", elapsed_s=5)  # -> comp-0 question

    # elapsed_s far exceeds this topic's 30s budget -> hard constraint
    # forces ADVANCE without needing multiple follow-up rounds.
    utterance = await engine.submit_candidate_answer("answer", elapsed_s=60)
    assert utterance.topic_id == "comp-1"


async def test_candidate_questions_then_closing() -> None:
    engine = _engine(n=1, time_budget_s=5)  # tiny budget -> advances immediately
    engine.start()
    await engine.submit_candidate_answer("Self introduction.", elapsed_s=5)  # -> comp-0 question

    to_candidate_questions = await engine.submit_candidate_answer("answer", elapsed_s=100)
    assert to_candidate_questions.kind == TurnKind.CANDIDATE_QUESTIONS

    closing = await engine.submit_candidate_answer("no questions from me", elapsed_s=110)
    assert closing.kind == TurnKind.CLOSING
    assert engine.is_complete


async def test_engine_resumes_from_saved_state() -> None:
    plan = _plan(n=2, time_budget_s=1000)
    engine = InterviewEngine(plan, Director(FakeLLMProvider(), provider_name="fake"))
    engine.start()
    await engine.submit_candidate_answer("Self introduction.", elapsed_s=5)  # -> comp-0 question
    await engine.submit_candidate_answer("thin", elapsed_s=10)  # -> follow_up

    saved_state = engine.state

    # Simulate a server restart: fresh engine, same plan, state reloaded
    # from wherever it was persisted (Postgres, per architecture.md §5).
    resumed = InterviewEngine(
        plan, Director(FakeLLMProvider(), provider_name="fake"), state=saved_state
    )
    assert resumed.current_probe is not None
    assert resumed.current_probe.id == "comp-0"
    assert resumed.state.progress.follow_ups_used == 1

    next_utterance = await resumed.submit_candidate_answer("more detail", elapsed_s=20)
    assert next_utterance.topic_id == "comp-1"


async def test_remaining_s_reflects_elapsed() -> None:
    engine = _engine()
    engine.start()
    await engine.submit_candidate_answer("answer", elapsed_s=100)
    assert engine.remaining_s == 900 - 100


def test_engine_state_defaults_are_fresh() -> None:
    state = EngineState()
    assert state.topic_index == 0
    assert state.elapsed_s == 0
    assert not state.complete
