import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.db.models.coding import CodingDifficulty, CodingSubmissionStatus

CodingLanguageLiteral = Literal["python", "csharp", "java"]


class CodingQuestionListItem(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    difficulty: CodingDifficulty

    model_config = {"from_attributes": True}


class CodingExample(BaseModel):
    input_display: str
    output_display: str
    explanation: str | None = None


class CodingQuestionDetail(BaseModel):
    slug: str
    title: str
    difficulty: CodingDifficulty
    description: str
    constraints: list[str]
    examples: list[CodingExample]
    starter_code: dict[str, str]


class SubmitRequest(BaseModel):
    language: CodingLanguageLiteral
    code: str = Field(min_length=1, max_length=20000)


class TestCaseResultResponse(BaseModel):
    test_case_id: uuid.UUID
    is_sample: bool
    passed: bool
    runtime_ms: int
    # None for hidden cases — grading-only, never reveal their inputs/expected
    # output or the stderr from running them (see app/api/coding.py).
    actual_output: Any | None = None
    expected_output: Any | None = None
    stderr: str | None = None


class SubmissionResponse(BaseModel):
    id: uuid.UUID
    status: CodingSubmissionStatus
    error_message: str | None
    results: list[TestCaseResultResponse]


class ReviewRequest(BaseModel):
    language: CodingLanguageLiteral
    code: str = Field(min_length=1, max_length=20000)


class HintRequest(BaseModel):
    language: CodingLanguageLiteral
    code: str = Field(min_length=1, max_length=20000)
    cursor_line: int | None = Field(default=None, ge=0)
    cursor_column: int | None = Field(default=None, ge=0)


class HintLogItem(BaseModel):
    created_at: datetime
    code_before: str
    hint_line: str
    cursor_line: int | None
    cursor_column: int | None

    model_config = {"from_attributes": True}


class ReviewLogItem(BaseModel):
    created_at: datetime
    code_reviewed: str
    review_text: str
    contained_code: bool

    model_config = {"from_attributes": True}


class AiUsageResponse(BaseModel):
    hints_used: int
    hint_limit: int
    hints: list[HintLogItem]
    reviews: list[ReviewLogItem]
