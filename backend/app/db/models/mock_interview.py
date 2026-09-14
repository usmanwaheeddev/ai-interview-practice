import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPk, str_enum_column


class MockInterviewState(StrEnum):
    PREPARING = "preparing"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    DISCONNECTED = "disconnected"
    COMPLETED = "completed"
    SCORING = "scoring"
    SCORED = "scored"
    FAILED = "failed"


class MockInterviewLanguage(StrEnum):
    PYTHON = "python"
    JAVA = "java"
    CSHARP = "csharp"


class MockInterviewLevel(StrEnum):
    BASIC = "basic"
    ADVANCED = "advanced"
    PRACTICAL = "practical"


class SpokenLanguage(StrEnum):
    """The human language the interview conversation is conducted in —
    independent of `language` above, which is the programming language for
    language-practice mode."""

    EN = "en"
    HI = "hi"
    UR = "ur"


# Exactly one of (resume_id, job_description) or (language, level) must be
# set — a mock interview is either resume/job-description driven or a
# language practice drill, never both and never neither.
_EXACTLY_ONE_MODE = (
    "(resume_id IS NOT NULL AND language IS NULL AND level IS NULL) "
    "OR (resume_id IS NULL AND job_description IS NULL "
    "AND language IS NOT NULL AND level IS NOT NULL)"
)


class MockInterview(UUIDPk, TimestampMixin, Base):
    __tablename__ = "mock_interviews"
    __table_args__ = (
        CheckConstraint("duration_minutes IN (15, 30)"),
        CheckConstraint(_EXACTLY_ONE_MODE, name="ck_mock_interviews_exactly_one_mode"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    resume_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="RESTRICT")
    )
    job_description: Mapped[str | None] = mapped_column(Text)
    language: Mapped[MockInterviewLanguage | None] = mapped_column(
        str_enum_column(MockInterviewLanguage, 10)
    )
    level: Mapped[MockInterviewLevel | None] = mapped_column(
        str_enum_column(MockInterviewLevel, 10)
    )
    spoken_language: Mapped[SpokenLanguage] = mapped_column(
        str_enum_column(SpokenLanguage, 5), default=SpokenLanguage.EN
    )
    topics: Mapped[list] = mapped_column(JSON, default=list)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    video_enabled: Mapped[bool] = mapped_column(default=False)
    state: Mapped[MockInterviewState] = mapped_column(
        str_enum_column(MockInterviewState, 20), default=MockInterviewState.PREPARING
    )
    interview_plan: Mapped[dict] = mapped_column(JSON, default=dict)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    elapsed_s: Mapped[int] = mapped_column(Integer, default=0)
    failure_reason: Mapped[str | None] = mapped_column(Text)


class MockInterviewTurn(UUIDPk, TimestampMixin, Base):
    __tablename__ = "mock_interview_turns"
    __table_args__ = (
        UniqueConstraint("interview_id", "turn_index"),
        CheckConstraint("speaker IN ('agent', 'user')"),
    )
    interview_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mock_interviews.id", ondelete="CASCADE"), index=True
    )
    turn_index: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MockMediaAsset(UUIDPk, TimestampMixin, Base):
    __tablename__ = "mock_media_assets"
    __table_args__ = (UniqueConstraint("interview_id", "chunk_index"),)
    interview_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mock_interviews.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(10))
    chunk_index: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(100))
    ready: Mapped[bool] = mapped_column(default=False)


class MockInterviewScore(UUIDPk, TimestampMixin, Base):
    __tablename__ = "mock_interview_scores"
    interview_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mock_interviews.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    overall: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    readiness: Mapped[str | None] = mapped_column(String(30))
    dimensions: Mapped[list] = mapped_column(JSON, default=list)
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    weaknesses: Mapped[list] = mapped_column(JSON, default=list)
    improvements: Mapped[list] = mapped_column(JSON, default=list)
    model: Mapped[str | None] = mapped_column(String(100))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
