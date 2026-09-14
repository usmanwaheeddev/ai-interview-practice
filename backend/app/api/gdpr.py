"""Personal data access and erasure for mock interview users."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.models import (
    MockInterview,
    MockInterviewScore,
    MockInterviewTurn,
    MockMediaAsset,
    Resume,
    User,
)
from app.db.session import get_db
from app.providers.storage import get_storage_provider

router = APIRouter(prefix="/me", tags=["personal-data"])


@router.get("/data-export")
async def export(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    interviews = list(
        (await db.scalars(select(MockInterview).where(MockInterview.user_id == user.id))).all()
    )
    ids = [i.id for i in interviews]

    def fields(row):
        return {column.name: getattr(row, column.name) for column in row.__table__.columns}

    return dict(
        user=dict(id=user.id, email=user.email, full_name=user.full_name),
        resumes=[
            fields(r) for r in await db.scalars(select(Resume).where(Resume.user_id == user.id))
        ],
        interviews=[fields(i) for i in interviews],
        turns=[
            fields(t)
            for t in await db.scalars(
                select(MockInterviewTurn).where(MockInterviewTurn.interview_id.in_(ids))
            )
        ],
        scores=[
            fields(s)
            for s in await db.scalars(
                select(MockInterviewScore).where(MockInterviewScore.interview_id.in_(ids))
            )
        ],
    )


@router.post("/erase", status_code=204)
async def erase(
    response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    ids = select(MockInterview.id).where(MockInterview.user_id == user.id)
    media = list(
        (await db.scalars(select(MockMediaAsset).where(MockMediaAsset.interview_id.in_(ids)))).all()
    )
    resumes = list((await db.scalars(select(Resume).where(Resume.user_id == user.id))).all())
    storage = get_storage_provider()
    for key in [m.storage_key for m in media] + [r.storage_key for r in resumes]:
        await storage.delete_object(key)
    await db.execute(delete(MockInterview).where(MockInterview.user_id == user.id))
    await db.execute(delete(Resume).where(Resume.user_id == user.id))
    await db.delete(user)
    await db.commit()
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
