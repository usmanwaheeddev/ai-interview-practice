import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.db.models import ParseStatus, Resume
from app.db.session import async_session_factory
from app.providers.llm import get_llm_provider
from app.providers.storage import get_storage_provider
from app.services.resume.extraction import extract_text

logger = get_logger(__name__)

EXTRACTION_PROMPT = (
    "Extract structured fields from this resume: email, phone, skills, "
    "work experience (employer, title, dates), and education. "
    "Return only what's actually present — never infer or invent."
)


async def parse_resume(ctx: dict[str, Any], resume_id: str) -> None:
    """Text extraction + structured extraction, run off the request path.
    Failure leaves parse_status=failed and is visible to the user — never a
    silently missing parse. See phases.md Phase 1 exit criteria."""
    storage = get_storage_provider()
    llm = get_llm_provider()

    async with async_session_factory() as db:
        resume = await db.get(Resume, uuid.UUID(resume_id))
        if resume is None:
            logger.warning("resume_parse.not_found", resume_id=resume_id)
            return

        try:
            data = await storage.get_object(resume.storage_key)
            raw_text = extract_text(data, content_type=resume.mime_type)
            resume.raw_text = raw_text
            parsed = await llm.extract_json(prompt=EXTRACTION_PROMPT, text=raw_text)

            resume.raw_text = raw_text
            resume.parsed = parsed
            resume.parse_status = ParseStatus.COMPLETE
            resume.parsed_at = datetime.now(UTC)
        except Exception:
            logger.exception("resume_parse.failed", resume_id=resume_id)
            resume.parse_status = ParseStatus.FAILED
            resume.parsed_at = datetime.now(UTC)

        await db.commit()
