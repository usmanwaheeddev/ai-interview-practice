from decimal import Decimal
from typing import Any

import pytest

from app.providers.llm.fake import FakeLLMProvider
from app.services.interview.director import (
    Director,
    DirectorAction,
    TopicProgress,
)
from app.services.interview.plan import TopicProbe


class ScriptedLLMProvider(FakeLLMProvider):
    """Returns a pre-set extract_json result — for testing Director branches
    that need real-looking LLM judgment output, which FakeLLMProvider (a
    resume-extraction heuristic) doesn't produce."""

    def __init__(self, scripted_result: dict[str, Any]) -> None:
        self._scripted_result = scripted_result

    async def extract_json(self, *, prompt: str, text: str) -> dict[str, Any]:
        return self._scripted_result


def _probe(**overrides: Any) -> TopicProbe:
    defaults: dict[str, Any] = {
        "id": "comp-1",
        "label": "Backend depth",
        "weight": Decimal("0.5"),
        "time_budget_s": 180,
        "primary_question": "Tell me about a hard bug you fixed.",
        "follow_up_hints": ["a specific tradeoff", "what broke", "what you'd do differently"],
    }
    defaults.update(overrides)
    return TopicProbe(**defaults)


async def test_provider_follow_up_then_advance() -> None:
    probe = _probe()
    progress = TopicProgress()

    first = await Director(
        ScriptedLLMProvider({"action": "follow_up", "text": "What broke?"})
    ).decide(probe=probe, progress=progress, candidate_answer="I fixed it.")
    assert first.action == DirectorAction.FOLLOW_UP
    assert first.text
    assert first.question_source == "groq"

    progress.follow_ups_used += 1
    second = await Director(ScriptedLLMProvider({"action": "advance"})).decide(
        probe=probe, progress=progress, candidate_answer="More detail."
    )
    assert second.action == DirectorAction.ADVANCE
    assert second.text == ""


async def test_budget_exhausted_forces_advance_without_asking_llm() -> None:
    probe = _probe(time_budget_s=60)
    progress = TopicProgress(block_elapsed_s=60)

    # A provider that would explode if called — proves the hard constraint
    # short-circuits before any LLM call happens.
    class ExplodingProvider(FakeLLMProvider):
        async def extract_json(self, *, prompt: str, text: str) -> dict[str, Any]:
            raise AssertionError("Director should not consult the LLM when budget is exhausted")

    director = Director(ExplodingProvider())
    decision = await director.decide(probe=probe, progress=progress, candidate_answer="anything")
    assert decision.action == DirectorAction.ADVANCE


async def test_max_follow_ups_forces_advance() -> None:
    probe = _probe()
    progress = TopicProgress(follow_ups_used=2)

    class ExplodingProvider(FakeLLMProvider):
        async def extract_json(self, *, prompt: str, text: str) -> dict[str, Any]:
            raise AssertionError("should not be called once follow-up cap is hit")

    director = Director(ExplodingProvider())
    decision = await director.decide(probe=probe, progress=progress, candidate_answer="anything")
    assert decision.action == DirectorAction.ADVANCE


async def test_llm_advance_judgment_respected() -> None:
    director = Director(ScriptedLLMProvider({"action": "advance"}))
    decision = await director.decide(
        probe=_probe(), progress=TopicProgress(), candidate_answer="A thorough answer."
    )
    assert decision.action == DirectorAction.ADVANCE


async def test_llm_follow_up_judgment_respected() -> None:
    director = Director(
        ScriptedLLMProvider({"action": "follow_up", "text": "What specifically broke?"})
    )
    decision = await director.decide(
        probe=_probe(), progress=TopicProgress(), candidate_answer="It broke once."
    )
    assert decision.action == DirectorAction.FOLLOW_UP
    assert decision.text == "What specifically broke?"
    assert decision.question_source == "groq"


async def test_llm_clarify_judgment_respected() -> None:
    director = Director(
        ScriptedLLMProvider({"action": "clarify", "text": "Sorry, could you repeat that?"})
    )
    decision = await director.decide(
        probe=_probe(), progress=TopicProgress(), candidate_answer="[inaudible]"
    )
    assert decision.action == DirectorAction.CLARIFY


async def test_llm_follow_up_without_text_is_rejected() -> None:
    director = Director(ScriptedLLMProvider({"action": "follow_up", "text": ""}))
    with pytest.raises(ValueError, match="invalid interview decision"):
        await director.decide(
            probe=_probe(), progress=TopicProgress(), candidate_answer="An answer."
        )


async def test_spoken_language_can_switch_mid_session() -> None:
    """`spoken_language` is a public, mutable attribute so the WS handler can
    re-point the Director at whatever language the candidate just spoke,
    turn by turn — see app/ws/interview.py's per-turn auto-switch."""
    director = Director(
        ScriptedLLMProvider({"action": "follow_up", "text": "Can you elaborate?"}),
        spoken_language="en",
    )
    decision = await director.decide(
        probe=_probe(), progress=TopicProgress(), candidate_answer="I fixed it."
    )
    assert decision.text == "Can you elaborate?"

    director.spoken_language = "hi"
    decision = await director.decide(
        probe=_probe(), progress=TopicProgress(), candidate_answer="I fixed it."
    )
    assert decision.text == "Can you elaborate?"
