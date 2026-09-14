import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.db.models import ParseStatus


class ResumeResponse(BaseModel):
    id: uuid.UUID
    filename: str
    mime_type: str
    parse_status: ParseStatus
    parsed: dict[str, Any]
    parsed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
