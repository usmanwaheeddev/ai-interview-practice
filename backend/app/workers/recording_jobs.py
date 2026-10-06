import uuid

from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.providers.storage import get_storage_provider
from app.services.interview.recording import create_master_recording

logger = get_logger(__name__)


async def combine_mock_recording(ctx: dict, interview_id: str) -> None:
    """Create the single recording shown in an interview report."""
    async with async_session_factory() as db:
        try:
            created = await create_master_recording(
                db, get_storage_provider(), uuid.UUID(interview_id)
            )
            if created:
                logger.info("mock_recording.combined", interview_id=interview_id)
        except Exception:
            # The report continues to show individual chunks until a later
            # reprocess succeeds, so a merge failure must not hide recordings.
            logger.exception("mock_recording.combine_failed", interview_id=interview_id)
