import uuid

from arq import ArqRedis
from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.resumes import ResumeResponse
from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.queue import get_queue
from app.db.models import Resume, User
from app.db.session import get_db
from app.providers.storage import get_storage_provider
from app.services.resume.extraction import ResumeValidationError, validate_resume_file

router = APIRouter(prefix="/resumes", tags=["resumes"])

_EXTENSION_BY_MIME = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


@router.post("", response_model=ResumeResponse, status_code=201)
async def upload_resume(
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_queue),
) -> Resume:
    data = await file.read()
    content_type = file.content_type or ""

    try:
        validate_resume_file(data, content_type=content_type)
    except ResumeValidationError as exc:
        raise ValidationAppError(str(exc), code="invalid_resume") from exc

    # Randomised storage key — architecture.md §8. Never trust the client's
    # filename for the storage path (path traversal, collisions).
    ext = _EXTENSION_BY_MIME[content_type]
    storage_key = f"resumes/{user.id}/{uuid.uuid4()}.{ext}"

    storage = get_storage_provider()
    await storage.put_object(storage_key, data, content_type=content_type)

    resume = Resume(
        user_id=user.id,
        storage_key=storage_key,
        filename=file.filename or f"resume.{ext}",
        mime_type=content_type,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)

    await queue.enqueue_job("parse_resume", str(resume.id))

    return resume


@router.get("", response_model=list[ResumeResponse])
async def list_my_resumes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Resume]:
    result = await db.execute(
        select(Resume).where(Resume.user_id == user.id).order_by(Resume.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Resume:
    resume = await db.get(Resume, resume_id)
    if resume is None or resume.user_id != user.id:
        raise NotFoundError("Resume not found", code="resume_not_found")
    return resume
