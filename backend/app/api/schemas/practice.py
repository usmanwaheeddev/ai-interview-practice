import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.db.models import MockInterviewState

PracticeTopic = Literal[
    "all_areas",
    "system_design",
    "programming",
    "problem_solving",
    "behavioral",
    "database",
    "architecture",
]
InterviewLanguage = Literal["python", "java", "csharp"]
InterviewLevel = Literal["basic", "advanced", "practical"]


class PracticeInterviewCreateRequest(BaseModel):
    """Either a resume interview (resume_id, topics; job_description optional)
    or a language-practice interview (language, level) — never both,
    never neither. See MockInterview's DB check constraint for the same rule
    enforced at the storage layer.

    The conversation's spoken language is never chosen here — every interview
    starts in English and the WS handler auto-detects and switches to
    whatever the candidate actually speaks, turn by turn."""

    job_description: str | None = Field(None, min_length=40, max_length=20000)
    resume_id: uuid.UUID | None = None
    topics: list[PracticeTopic] | None = Field(None, min_length=1, max_length=6)
    language: InterviewLanguage | None = None
    level: InterviewLevel | None = None
    duration_minutes: Literal[15, 30]
    video_enabled: bool = False

    @model_validator(mode="after")
    def check_exactly_one_mode(self) -> "PracticeInterviewCreateRequest":
        resume_mode = bool(self.resume_id is not None and self.topics)
        language_mode = bool(self.language is not None and self.level is not None)
        if resume_mode == language_mode:
            raise ValueError(
                "Provide either resume_id/topics or language/level, "
                "not both/neither"
            )
        return self


class PracticeInterviewResponse(BaseModel):
    id: uuid.UUID
    resume_id: uuid.UUID | None
    topics: list[str]
    language: str | None
    level: str | None
    spoken_language: str
    duration_minutes: int
    video_enabled: bool
    state: MockInterviewState
    elapsed_s: int
    remaining_s: int
    failure_reason: str | None
    created_at: datetime


class MediaUploadRequest(BaseModel):
    kind: Literal["audio", "video"]
    chunk_index: int = Field(ge=0, le=10000)
    content_type: str = Field(max_length=100)


class MediaCompleteRequest(BaseModel):
    chunk_indices: list[int] = Field(max_length=10000)
