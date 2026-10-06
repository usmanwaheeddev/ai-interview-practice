"""Create master playback files for every existing mock interview recording."""

import asyncio

from sqlalchemy import func, select

from app.db.models import MockMediaAsset
from app.db.session import async_session_factory
from app.providers.storage import get_storage_provider
from app.services.interview.recording import create_master_recording, ffmpeg_available


async def main() -> None:
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg is required to reprocess recordings")
    async with async_session_factory() as db:
        total_assets = await db.scalar(select(func.count()).select_from(MockMediaAsset))
        interview_ids = list(
            (
                await db.scalars(
                    select(MockMediaAsset.interview_id)
                    .where(
                        MockMediaAsset.ready.is_(True),
                        MockMediaAsset.chunk_index >= 0,
                    )
                    .distinct()
                )
            ).all()
        )
        print(
            f"Found {len(interview_ids)} interview(s) with ready recording chunks "
            f"out of {total_assets or 0} stored media asset(s).",
            flush=True,
        )
        completed = failed = 0
        for interview_id in interview_ids:
            try:
                if await create_master_recording(db, get_storage_provider(), interview_id):
                    completed += 1
                    print(f"Combined recording for {interview_id}", flush=True)
            except Exception as exc:
                failed += 1
                print(f"Could not combine {interview_id}: {exc}", flush=True)
        print(f"Completed: {completed}; failed: {failed}", flush=True)
        if failed:
            raise RuntimeError("One or more recordings could not be reprocessed")


if __name__ == "__main__":
    asyncio.run(main())
