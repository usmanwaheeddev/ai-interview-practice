import uuid
from datetime import UTC, datetime

from arq import ArqRedis
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.practice import (
    MediaCompleteRequest,
    MediaUploadRequest,
    PracticeInterviewCreateRequest,
    PracticeInterviewResponse,
)
from app.core.deps import get_current_user
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.queue import get_queue
from app.db.models import (
    MockInterview,
    MockInterviewScore,
    MockInterviewState,
    MockInterviewTurn,
    MockMediaAsset,
    Resume,
    User,
)
from app.db.session import get_db
from app.providers.storage import get_storage_provider

router = APIRouter(prefix="/mock-interviews", tags=["mock-interviews"])


async def owned(
    interview_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MockInterview:
    interview = await db.get(MockInterview, interview_id)
    if interview is None or interview.user_id != user.id:
        raise NotFoundError("Mock interview not found", code="interview_not_found")
    return interview


def response(i: MockInterview) -> PracticeInterviewResponse:
    return PracticeInterviewResponse(
        id=i.id,
        resume_id=i.resume_id,
        topics=i.topics,
        language=i.language,
        level=i.level,
        spoken_language=i.spoken_language,
        duration_minutes=i.duration_minutes,
        video_enabled=i.video_enabled,
        state=i.state,
        elapsed_s=i.elapsed_s,
        remaining_s=max(0, i.duration_minutes * 60 - i.elapsed_s),
        failure_reason=i.failure_reason,
        created_at=i.created_at,
    )


@router.post("", response_model=PracticeInterviewResponse, status_code=201)
async def create_interview(
    body: PracticeInterviewCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_queue),
):
    if body.language is not None:
        interview = MockInterview(
            user_id=user.id,
            language=body.language,
            level=body.level,
            topics=[],
            duration_minutes=body.duration_minutes,
            video_enabled=body.video_enabled,
        )
    else:
        resume = await db.get(Resume, body.resume_id)
        if resume is None or resume.user_id != user.id:
            raise NotFoundError("Resume not found", code="resume_not_found")
        interview = MockInterview(
            user_id=user.id,
            resume_id=body.resume_id,
            job_description=body.job_description,
            topics=body.topics,
            duration_minutes=body.duration_minutes,
            video_enabled=body.video_enabled,
        )
    db.add(interview)
    await db.commit()
    await db.refresh(interview)
    try:
        await queue.enqueue_job("generate_mock_plan", str(interview.id))
    except Exception:
        interview.state = MockInterviewState.FAILED
        interview.failure_reason = "Could not queue interview preparation. Please retry."
        await db.commit()
    return response(interview)


@router.get("", response_model=list[PracticeInterviewResponse])
async def list_interviews(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    interviews = await db.scalars(
        select(MockInterview)
        .where(MockInterview.user_id == user.id)
        .order_by(MockInterview.created_at.desc())
    )
    return [response(i) for i in interviews]


@router.get("/{interview_id}", response_model=PracticeInterviewResponse)
async def get_interview(interview: MockInterview = Depends(owned)):
    return response(interview)


@router.post("/{interview_id}/retry", response_model=PracticeInterviewResponse)
async def retry_plan(
    interview: MockInterview = Depends(owned),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_queue),
):
    if interview.state not in (MockInterviewState.FAILED, MockInterviewState.PREPARING):
        raise ConflictError("This interview is already prepared", code="invalid_state")
    interview.state = MockInterviewState.PREPARING
    interview.failure_reason = None
    await db.commit()
    try:
        await queue.enqueue_job("generate_mock_plan", str(interview.id))
    except Exception:
        interview.state = MockInterviewState.FAILED
        interview.failure_reason = "Could not queue interview preparation. Please retry."
        await db.commit()
    return response(interview)


@router.post("/{interview_id}/consent", response_model=PracticeInterviewResponse)
async def consent(interview: MockInterview = Depends(owned), db: AsyncSession = Depends(get_db)):
    if interview.state not in (
        MockInterviewState.READY,
        MockInterviewState.DISCONNECTED,
        MockInterviewState.IN_PROGRESS,
    ):
        raise ConflictError("Interview is not ready", code="invalid_state")
    interview.consent_at = datetime.now(UTC)
    await db.commit()
    return response(interview)


@router.post("/{interview_id}/rescore", status_code=202)
async def rescore(
    interview: MockInterview = Depends(owned),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_queue),
):
    if interview.state not in (MockInterviewState.COMPLETED, MockInterviewState.SCORED):
        raise ConflictError("Finish the interview before requesting feedback", code="invalid_state")
    interview.state = MockInterviewState.SCORING
    score = await db.scalar(
        select(MockInterviewScore).where(MockInterviewScore.interview_id == interview.id)
    )
    if score:
        score.status = "pending"
        score.failure_reason = None
    await db.commit()
    try:
        await queue.enqueue_job("score_mock_interview", str(interview.id))
    except Exception:
        interview.state = MockInterviewState.COMPLETED
        interview.failure_reason = "Report queue unavailable. Please retry."
        if score:
            score.status = "failed"
            score.failure_reason = interview.failure_reason
        await db.commit()
        raise ConflictError(interview.failure_reason, code="queue_unavailable") from None
    return {"status": "pending"}


@router.get("/{interview_id}/report")
async def report(interview: MockInterview = Depends(owned), db: AsyncSession = Depends(get_db)):
    score = await db.scalar(
        select(MockInterviewScore).where(MockInterviewScore.interview_id == interview.id)
    )
    turns = await db.scalars(
        select(MockInterviewTurn)
        .where(MockInterviewTurn.interview_id == interview.id)
        .order_by(MockInterviewTurn.turn_index)
    )
    media = await db.scalars(
        select(MockMediaAsset)
        .where(MockMediaAsset.interview_id == interview.id, MockMediaAsset.ready.is_(True))
        .order_by(MockMediaAsset.chunk_index)
    )
    storage = get_storage_provider()
    return dict(
        state=interview.state,
        score_status=score.status if score else None,
        overall_score=score.overall if score else None,
        readiness=score.readiness if score else None,
        strengths=score.strengths if score else [],
        weaknesses=score.weaknesses if score else [],
        improvements=score.improvements if score else [],
        dimensions=score.dimensions if score else [],
        failure_reason=score.failure_reason if score else interview.failure_reason,
        transcript=[dict(speaker=t.speaker, text=t.text, turn_index=t.turn_index) for t in turns],
        recordings=[
            dict(
                kind=m.kind,
                chunk_index=m.chunk_index,
                url=await storage.get_presigned_url(m.storage_key),
            )
            for m in media
        ],
    )


@router.post("/{interview_id}/media")
async def upload_media(
    body: MediaUploadRequest,
    interview: MockInterview = Depends(owned),
    db: AsyncSession = Depends(get_db),
):
    expected = "video" if interview.video_enabled else "audio"
    if body.kind != expected or not body.content_type.startswith(expected + "/"):
        raise ValidationAppError(
            "Recording type does not match selected interview mode", code="invalid_media"
        )
    if interview.consent_at is None or interview.started_at is None:
        raise ConflictError(
            "Recording requires a started, consented interview", code="invalid_state"
        )
    asset = await db.scalar(
        select(MockMediaAsset).where(
            MockMediaAsset.interview_id == interview.id,
            MockMediaAsset.chunk_index == body.chunk_index,
        )
    )
    if asset is None:
        asset = MockMediaAsset(
            interview_id=interview.id,
            kind=body.kind,
            chunk_index=body.chunk_index,
            storage_key=f"mock-interviews/{interview.id}/{body.kind}/chunk-{body.chunk_index:05d}.webm",
            content_type=body.content_type,
        )
        db.add(asset)
        await db.commit()
    return dict(
        upload_url=await get_storage_provider().get_presigned_put_url(
            asset.storage_key, content_type=asset.content_type
        ),
        storage_key=asset.storage_key,
    )


@router.post("/{interview_id}/media/complete", status_code=204)
async def complete_media(
    body: MediaCompleteRequest,
    interview: MockInterview = Depends(owned),
    db: AsyncSession = Depends(get_db),
):
    assets = await db.scalars(
        select(MockMediaAsset).where(
            MockMediaAsset.interview_id == interview.id,
            MockMediaAsset.chunk_index.in_(body.chunk_indices),
        )
    )
    for asset in assets:
        asset.ready = True
    await db.commit()
