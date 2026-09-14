import uuid
from enum import StrEnum

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPk, str_enum_column


class CodingDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class CodingLanguage(StrEnum):
    PYTHON = "python"
    CSHARP = "csharp"
    JAVA = "java"


class CodingSubmissionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class CodingQuestion(UUIDPk, TimestampMixin, Base):
    __tablename__ = "coding_questions"

    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    difficulty: Mapped[CodingDifficulty] = mapped_column(str_enum_column(CodingDifficulty, 10))
    description: Mapped[str] = mapped_column(Text)
    constraints: Mapped[list] = mapped_column(JSON, default=list)
    examples: Mapped[list] = mapped_column(JSON, default=list)
    class_name: Mapped[str] = mapped_column(String(100), default="Solution")
    # {"name": str, "params": [{"name": str, "type": str}], "return_type": str}
    # — see app.services.coding.signature for the supported `type` values.
    function_signature: Mapped[dict] = mapped_column(JSON)
    # Keyed by CodingLanguage value ("python"/"csharp"/"java") -> source string.
    starter_code: Mapped[dict] = mapped_column(JSON)


class CodingTestCase(UUIDPk, TimestampMixin, Base):
    __tablename__ = "coding_test_cases"
    __table_args__ = (UniqueConstraint("question_id", "order"),)

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("coding_questions.id", ondelete="CASCADE"), index=True
    )
    # Positional, matching function_signature.params order — e.g. [[2,7,11,15], 9]
    args: Mapped[list] = mapped_column(JSON)
    expected_output: Mapped[object] = mapped_column(JSON)
    # Sample cases are safe to show the candidate; hidden ones are grading-only
    # and must never reach the frontend beyond pass/fail — see app/api/coding.py.
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer)


class CodingSubmission(UUIDPk, TimestampMixin, Base):
    __tablename__ = "coding_submissions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("coding_questions.id", ondelete="CASCADE"), index=True
    )
    language: Mapped[CodingLanguage] = mapped_column(str_enum_column(CodingLanguage, 10))
    code: Mapped[str] = mapped_column(Text)
    status: Mapped[CodingSubmissionStatus] = mapped_column(
        str_enum_column(CodingSubmissionStatus, 10), default=CodingSubmissionStatus.PENDING
    )
    # Per-test-case list of {test_case_id, passed, actual_output, expected_output,
    # stderr, runtime_ms} — includes hidden cases' expected/actual for internal
    # debugging; the API response layer (app/api/coding.py) strips those fields
    # for hidden cases before returning to the client.
    results: Mapped[list] = mapped_column(JSON, default=list)
    error_message: Mapped[str | None] = mapped_column(Text)


class CodingHintConfig(UUIDPk, TimestampMixin, Base):
    """A single default row read by app.services.coding.ai_assist — kept as
    a table rather than a Settings field so the hint limit is editable
    without a redeploy, and so a later per-user override table has
    somewhere natural to join against instead of a hardcoded constant."""

    __tablename__ = "coding_hint_configs"

    default_hint_limit: Mapped[int] = mapped_column(Integer, default=2)


class CodingHintUsage(UUIDPk, TimestampMixin, Base):
    __tablename__ = "coding_hint_usages"
    __table_args__ = (UniqueConstraint("user_id", "question_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("coding_questions.id", ondelete="CASCADE"), index=True
    )
    hints_used: Mapped[int] = mapped_column(Integer, default=0)


class CodingHintLog(UUIDPk, TimestampMixin, Base):
    """Full-content log of every hint actually granted — lets the candidate
    (see the self-scoped /ai-usage endpoint) see exactly what assistance
    they used on a question."""

    __tablename__ = "coding_hint_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("coding_questions.id", ondelete="CASCADE"), index=True
    )
    language: Mapped[CodingLanguage] = mapped_column(str_enum_column(CodingLanguage, 10))
    code_before: Mapped[str] = mapped_column(Text)
    hint_line: Mapped[str] = mapped_column(Text)
    cursor_line: Mapped[int | None] = mapped_column(Integer)
    cursor_column: Mapped[int | None] = mapped_column(Integer)


class CodingReviewLog(UUIDPk, TimestampMixin, Base):
    __tablename__ = "coding_review_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("coding_questions.id", ondelete="CASCADE"), index=True
    )
    language: Mapped[CodingLanguage] = mapped_column(str_enum_column(CodingLanguage, 10))
    code_reviewed: Mapped[str] = mapped_column(Text)
    review_text: Mapped[str] = mapped_column(Text)
    # The model was explicitly instructed never to include code — this flags
    # the rare case where it did anyway (defensively passed through as-is,
    # never surgically stripped), so prompt tuning has real signal.
    contained_code: Mapped[bool] = mapped_column(Boolean, default=False)
