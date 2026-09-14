import uuid

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import MockInterview, MockInterviewState, ParseStatus, Resume
from app.db.session import async_session_factory
from app.providers.llm import get_llm_provider
from app.services.interview.memory import load_user_memory
from app.services.interview.plan import generate_interview_plan, generate_language_interview_plan
from app.workers.resume_jobs import parse_resume

logger = get_logger(__name__)


async def generate_mock_plan(ctx: dict, interview_id: str) -> None:
    async with async_session_factory() as db:
        interview = await db.scalar(
            select(MockInterview)
            .where(MockInterview.id == uuid.UUID(interview_id))
            .with_for_update()
        )
        if interview is None or interview.state != MockInterviewState.PREPARING:
            return
        try:
            memory_context = await load_user_memory(
                db, interview.user_id, exclude_interview_id=interview.id
            )
            if interview.language is not None:
                plan = await generate_language_interview_plan(
                    interview=interview,
                    llm=get_llm_provider(),
                    provider_name=get_settings().llm_provider,
                    spoken_language="en",
                    memory_context=memory_context,
                )
            else:
                resume = await db.get(Resume, interview.resume_id)
                if resume is None:
                    raise ValueError("Resume no longer exists")
                if resume.parse_status != ParseStatus.COMPLETE:
                    await parse_resume(ctx, str(resume.id))
                    await db.refresh(resume)
                if not resume.raw_text:
                    raise ValueError("Resume could not be read. Upload a readable PDF or DOCX.")
                plan = await generate_interview_plan(
                    interview=interview,
                    resume=resume,
                    llm=get_llm_provider(),
                    provider_name=get_settings().llm_provider,
                    spoken_language="en",
                    memory_context=memory_context,
                )
            interview.interview_plan = plan.model_dump(mode="json")
            interview.state = MockInterviewState.READY
            interview.failure_reason = None
            logger.info("mock_plan.created", interview_id=interview_id, fallback=plan.fallback_used)
        except Exception as exc:
            logger.exception("mock_plan.failed", interview_id=interview_id)
            interview.state = MockInterviewState.FAILED
            interview.failure_reason = (
                str(exc)
                if isinstance(exc, ValueError)
                else "Could not prepare interview. Please retry."
            )
        await db.commit()
