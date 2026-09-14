from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.services.interview.plan import InterviewPlan, TopicProbe
from app.services.scoring.scorer import score_session


class StructuredOnlyLLM:
    async def extract_json(self, *, prompt: str, text: str) -> dict:
        assert "SCORING_TASK_V1" in prompt
        assert "JSON object" in text
        return {
            "value": 4,
            "reasoning": "The answer described an explicit reliability technique.",
            "evidence": ["I used idempotency keys for payment retries."],
            "improvement": "Compare database and cache-based deduplication.",
        }

    async def complete(self, *, system: str, user: str, max_tokens: int = 60) -> str:
        raise AssertionError("scoring must not use free-form completion")


async def test_scoring_uses_structured_provider_path() -> None:
    plan = InterviewPlan(
        topics=[
            TopicProbe(
                id="system_design",
                label="System design",
                description="Reliability",
                weight=Decimal("1"),
                time_budget_s=60,
                primary_question="How do you make retries safe?",
            )
        ]
    )
    turn = SimpleNamespace(
        speaker="user",
        text="I used idempotency keys for payment retries.",
        started_at=datetime.now(UTC),
    )

    result = await score_session(
        llm=StructuredOnlyLLM(),  # type: ignore[arg-type]
        plan=plan,
        turns=[turn],
        user_name="Candidate",
        user_email="candidate@example.com",
    )

    assert result["overall"] == Decimal("4.00")
    assert result["status"] == "complete"
