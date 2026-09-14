import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import (
    MockInterview,
    MockInterviewScore,
    MockInterviewState,
    MockInterviewTurn,
    User,
)
from app.db.session import async_session_factory
from app.providers.llm import get_llm_provider
from app.services.interview.plan import InterviewPlan
from app.services.scoring.scorer import score_session

logger = get_logger(__name__)


async def score_mock_interview(ctx: dict, interview_id: str) -> None:
    async with async_session_factory() as db:
        interview = await db.scalar(
            select(MockInterview)
            .where(MockInterview.id == uuid.UUID(interview_id))
            .with_for_update()
        )
        if interview is None or interview.state != MockInterviewState.SCORING:
            return
        score = await db.scalar(
            select(MockInterviewScore).where(MockInterviewScore.interview_id == interview.id)
        )
        if score is None:
            score = MockInterviewScore(interview_id=interview.id)
            db.add(score)
        try:
            user = await db.get(User, interview.user_id)
            if user is None:
                raise ValueError("User no longer exists")
            turns = list(
                (
                    await db.scalars(
                        select(MockInterviewTurn)
                        .where(MockInterviewTurn.interview_id == interview.id)
                        .order_by(MockInterviewTurn.turn_index)
                    )
                ).all()
            )
            result = await score_session(
                llm=get_llm_provider(),
                plan=InterviewPlan.model_validate(interview.interview_plan),
                turns=turns,
                user_name=user.full_name,
                user_email=user.email,
                spoken_language="en",
            )
            for key, value in result.items():
                setattr(score, key, value)
            score.model = get_settings().llm_provider
            score.scored_at = datetime.now(UTC)
            score.failure_reason = None
            interview.state = MockInterviewState.SCORED
            logger.info("mock_score.completed", interview_id=interview_id)
        except Exception as exc:
            logger.exception("mock_score.failed", interview_id=interview_id)
            score.status = "failed"
            score.failure_reason = (
                str(exc)
                if isinstance(exc, ValueError)
                else "Scoring service unavailable. Retry your report shortly."
            )
            interview.state = MockInterviewState.COMPLETED
        await db.commit()
