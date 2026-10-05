import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.db.models import MockInterviewState
from app.services.interview.fields import INTERVIEW_FIELD_IDS, areas_for_field

InterviewLanguage = Literal["python", "java", "csharp"]
InterviewLevel = Literal["basic", "advanced", "practical"]


class PracticeInterviewCreateRequest(BaseModel):
    """Either a resume interview (resume_id, topics; job_description optional)
    or a language-practice interview (language, level) — never both,
    never neither. See MockInterview's DB check constraint for the same rule
    enforced at the storage layer.

    The conversation's spoken language is never chosen here. The current live
    interview transport transcribes and speaks English."""

    job_description: str | None = Field(None, min_length=40, max_length=20000)
    resume_id: uuid.UUID | None = None
    field_type: str | None = None
    topics: list[str] | None = Field(None, min_length=1, max_length=6)
    language: InterviewLanguage | None = None
    level: InterviewLevel | None = None
    duration_minutes: Literal[15, 30]
    video_enabled: bool = False

    @model_validator(mode="after")
    def check_exactly_one_mode(self) -> "PracticeInterviewCreateRequest":
        if self.resume_id is not None:
            if (
                not self.field_type
                or not self.topics
                or self.language is not None
                or self.level is not None
            ):
                raise ValueError("Resume interviews require one field and one or more areas")
            resume_mode = True
        elif self.language is not None or self.level is not None:
            if (
                self.language is None
                or self.level is None
                or self.job_description is not None
                or self.field_type is not None
                or self.topics is not None
            ):
                raise ValueError("Language interviews cannot include a field or areas")
            resume_mode = False
        else:
            raise ValueError("Provide either resume_id/topics or language/level, not both/neither")
        if resume_mode:
            if self.field_type not in INTERVIEW_FIELD_IDS:
                raise ValueError("Select a supported interview field")
            assert self.topics is not None and self.field_type is not None
            allowed = set(areas_for_field(self.field_type))
            if self.topics == ["all_areas"]:
                return self
            if "all_areas" in self.topics:
                raise ValueError("All areas cannot be combined with individual areas")
            if len(set(self.topics)) != len(self.topics) or not set(self.topics) <= allowed:
                raise ValueError("Every selected area must belong to the selected field")
        return self


class PracticeInterviewResponse(BaseModel):
    id: uuid.UUID
    resume_id: uuid.UUID | None
    field_type: str | None
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
