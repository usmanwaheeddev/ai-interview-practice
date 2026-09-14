import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.schemas.coding import (
    AiUsageResponse,
    CodingQuestionDetail,
    CodingQuestionListItem,
    HintLogItem,
    HintRequest,
    ReviewLogItem,
    ReviewRequest,
    SubmissionResponse,
    SubmitRequest,
    TestCaseResultResponse,
)
from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError, TooManyRequestsError
from app.core.logging import get_logger
from app.core.sse import format_sse
from app.db.models import (
    CodingHintLog,
    CodingHintUsage,
    CodingQuestion,
    CodingReviewLog,
    CodingSubmission,
    CodingTestCase,
    User,
)
from app.db.models.coding import CodingLanguage
from app.db.session import get_db, get_session_factory
from app.providers.execution import get_execution_provider
from app.providers.llm import stream_complete_with_fallback
from app.services.coding.ai_assist import (
    HINT_SYSTEM_PROMPT,
    MIN_REVIEW_AUTHORED_LINES,
    REVIEW_SYSTEM_PROMPT,
    build_hint_prompt,
    build_review_prompt,
    count_authored_lines,
    get_hint_limit,
    get_or_create_hint_usage,
)
from app.services.coding.runner import TestCaseResult, run_submission

router = APIRouter(prefix="/coding-questions", tags=["coding-questions"])
logger = get_logger(__name__)


async def _get_question_or_404(slug: str, db: AsyncSession) -> CodingQuestion:
    question = await db.scalar(select(CodingQuestion).where(CodingQuestion.slug == slug))
    if question is None:
        raise NotFoundError("Coding question not found", code="question_not_found")
    return question


def _result_response(result: TestCaseResult, *, is_sample: bool) -> TestCaseResultResponse:
    # Hidden cases are grading-only — pass/fail and runtime only, never their
    # inputs, expected/actual output, or stderr (which could leak them).
    return TestCaseResultResponse(
        test_case_id=uuid.UUID(result.test_case_id),
        is_sample=is_sample,
        passed=result.passed,
        runtime_ms=result.runtime_ms,
        actual_output=result.actual_output if is_sample else None,
        expected_output=result.expected_output if is_sample else None,
        stderr=result.stderr if is_sample else None,
    )


@router.get("", response_model=list[CodingQuestionListItem])
async def list_questions(db: AsyncSession = Depends(get_db)) -> list[CodingQuestion]:
    questions = await db.scalars(select(CodingQuestion).order_by(CodingQuestion.created_at))
    return list(questions)


@router.get("/{slug}", response_model=CodingQuestionDetail)
async def get_question(slug: str, db: AsyncSession = Depends(get_db)) -> CodingQuestionDetail:
    question = await _get_question_or_404(slug, db)
    return CodingQuestionDetail(
        slug=question.slug,
        title=question.title,
        difficulty=question.difficulty,
        description=question.description,
        constraints=question.constraints,
        examples=question.examples,
        starter_code=question.starter_code,
    )


@router.post("/{slug}/submit", response_model=SubmissionResponse, status_code=201)
async def submit(
    slug: str,
    body: SubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubmissionResponse:
    question = await _get_question_or_404(slug, db)
    test_cases = list(
        await db.scalars(
            select(CodingTestCase)
            .where(CodingTestCase.question_id == question.id)
            .order_by(CodingTestCase.order)
        )
    )
    sample_ids = {str(tc.id) for tc in test_cases if tc.is_sample}

    outcome = await run_submission(
        execution_provider=get_execution_provider(),
        settings=get_settings(),
        question=question,
        test_cases=test_cases,
        language=CodingLanguage(body.language),
        code=body.code,
    )

    submission = CodingSubmission(
        user_id=user.id,
        question_id=question.id,
        language=CodingLanguage(body.language),
        code=body.code,
        status=outcome.status,
        results=[
            {
                "test_case_id": r.test_case_id,
                "passed": r.passed,
                "actual_output": r.actual_output,
                "expected_output": r.expected_output,
                "stderr": r.stderr,
                "runtime_ms": r.runtime_ms,
            }
            for r in outcome.results
        ],
        error_message=outcome.error_message,
    )
    db.add(submission)
    await db.commit()

    return SubmissionResponse(
        id=submission.id,
        status=submission.status,
        error_message=submission.error_message,
        results=[
            _result_response(r, is_sample=r.test_case_id in sample_ids) for r in outcome.results
        ],
    )


@router.post("/{slug}/review")
async def review(
    slug: str,
    body: ReviewRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> StreamingResponse:
    """Streams free-form prose feedback on the candidate's current,
    unsubmitted code — never code or a rewritten solution (see
    REVIEW_SYSTEM_PROMPT). If the model includes a code fence anyway, it's
    still streamed through as-is (surgically stripping it can corrupt the
    response) and flagged via `contained_code` on the persisted log row.

    Skips the LLM call entirely — no log row either, since nothing was
    actually reviewed — when the candidate hasn't written enough code yet
    beyond the starter skeleton (see MIN_REVIEW_AUTHORED_LINES): asking a
    model to review an empty or near-empty solution just produces
    generic filler."""
    question = await _get_question_or_404(slug, db)
    starter = question.starter_code.get(body.language, "")
    authored_lines = count_authored_lines(starter, body.code)
    prompt = build_review_prompt(question, body.language, body.code)
    user_id, question_id = user.id, question.id

    async def event_stream():
        if authored_lines < MIN_REVIEW_AUTHORED_LINES:
            yield format_sse(
                "Write a bit more of your solution before requesting a review — "
                "there's not enough here yet to say anything useful about."
            )
            yield format_sse(json.dumps({"contained_code": False}), event="done")
            return

        chunks: list[str] = []
        try:
            async for chunk in stream_complete_with_fallback(
                system=REVIEW_SYSTEM_PROMPT, user=prompt, max_tokens=700
            ):
                chunks.append(chunk)
                yield format_sse(chunk)
        except Exception as exc:
            logger.warning(
                "coding.review_stream_failed", slug=slug, error=str(exc), exc_info=True
            )
            yield format_sse("The AI review failed. Please try again.", event="error")
            return

        review_text = "".join(chunks)
        contained_code = "```" in review_text
        # A fresh session, not the request's injected `db`: FastAPI closes
        # yield-based dependencies as soon as the route function *returns*,
        # not once a StreamingResponse finishes sending — by the time this
        # generator runs (driven later by Starlette), `db`'s transaction is
        # already gone. See app/db/session.py's async_session_factory.
        async with session_factory() as write_db:
            write_db.add(
                CodingReviewLog(
                    user_id=user_id,
                    question_id=question_id,
                    language=CodingLanguage(body.language),
                    code_reviewed=body.code,
                    review_text=review_text,
                    contained_code=contained_code,
                )
            )
            await write_db.commit()
        yield format_sse(json.dumps({"contained_code": contained_code}), event="done")

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{slug}/hint")
async def hint(
    slug: str,
    body: HintRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> StreamingResponse:
    """Streams exactly the next line of code at the candidate's cursor,
    capped by CodingHintConfig.default_hint_limit per (user, question). The
    limit is enforced *before* calling the LLM at all, and hints_used is
    only incremented after a hint is fully and successfully streamed — a
    failed generation doesn't cost the candidate a hint."""
    question = await _get_question_or_404(slug, db)
    limit = await get_hint_limit(db)
    usage = await get_or_create_hint_usage(db, user.id, question.id)
    # Durably persist any lazily-created config/usage row now, while `db`'s
    # transaction is still open (see the note in event_stream() below about
    # why this session can't be relied on any later than this point).
    await db.commit()
    if usage.hints_used >= limit:
        raise TooManyRequestsError(
            f"Hint limit reached ({limit} hints for this question)", code="hint_limit_reached"
        )

    prompt = build_hint_prompt(
        question, body.language, body.code, body.cursor_line, body.cursor_column
    )
    user_id, question_id = user.id, question.id

    async def event_stream():
        collected: list[str] = []
        try:
            async for chunk in stream_complete_with_fallback(
                system=HINT_SYSTEM_PROMPT, user=prompt, max_tokens=120
            ):
                # Defensive truncation: models don't always respect "one line
                # only" — treat anything from the first newline on as not
                # part of the hint, whichever provider produced it.
                if "\n" in chunk:
                    before = chunk.split("\n", 1)[0]
                    if before:
                        collected.append(before)
                        yield format_sse(before)
                    break
                collected.append(chunk)
                yield format_sse(chunk)
        except Exception as exc:
            logger.warning("coding.hint_stream_failed", slug=slug, error=str(exc), exc_info=True)
            yield format_sse("The AI hint failed. Please try again.", event="error")
            return

        hint_line = "".join(collected)
        # A fresh session, not the request's injected `db` — see review()'s
        # matching comment: it's already closed by the time this generator
        # runs, so re-fetching (rather than reusing) `usage` here is required,
        # not just defensive.
        async with session_factory() as write_db:
            usage_row = await get_or_create_hint_usage(write_db, user_id, question_id)
            usage_row.hints_used += 1
            write_db.add(
                CodingHintLog(
                    user_id=user_id,
                    question_id=question_id,
                    language=CodingLanguage(body.language),
                    code_before=body.code,
                    hint_line=hint_line,
                    cursor_line=body.cursor_line,
                    cursor_column=body.cursor_column,
                )
            )
            await write_db.commit()
            hints_used_after = usage_row.hints_used

        yield format_sse(
            json.dumps({"hints_used": hints_used_after, "hint_limit": limit}), event="done"
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{slug}/ai-usage", response_model=AiUsageResponse)
async def ai_usage(
    slug: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiUsageResponse:
    """Self-scoped only — the current user's own hint/review history for
    this question. This app has no recruiter/interviewer role (see
    CLAUDE.md), so unlike a cross-candidate report this never takes another
    user's id."""
    question = await _get_question_or_404(slug, db)
    limit = await get_hint_limit(db)
    usage = await db.scalar(
        select(CodingHintUsage).where(
            CodingHintUsage.user_id == user.id, CodingHintUsage.question_id == question.id
        )
    )
    hints = await db.scalars(
        select(CodingHintLog)
        .where(CodingHintLog.user_id == user.id, CodingHintLog.question_id == question.id)
        .order_by(CodingHintLog.created_at)
    )
    reviews = await db.scalars(
        select(CodingReviewLog)
        .where(CodingReviewLog.user_id == user.id, CodingReviewLog.question_id == question.id)
        .order_by(CodingReviewLog.created_at)
    )
    await db.commit()

    return AiUsageResponse(
        hints_used=usage.hints_used if usage else 0,
        hint_limit=limit,
        hints=[HintLogItem.model_validate(h) for h in hints],
        reviews=[ReviewLogItem.model_validate(r) for r in reviews],
    )
