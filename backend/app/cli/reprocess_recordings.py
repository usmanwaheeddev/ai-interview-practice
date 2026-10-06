"""Create master playback files for every existing mock interview recording."""

import argparse
import asyncio
from collections import defaultdict

from sqlalchemy import func, select

from app.db.models import MockMediaAsset
from app.db.session import async_session_factory
from app.providers.storage import get_storage_provider
from app.services.interview.recording import create_master_recording, ffmpeg_available


async def repair_ready_assets() -> tuple[int, int]:
    """Safely recover old uploads that reached storage but missed completion."""
    repaired = skipped = 0
    storage = get_storage_provider()
    async with async_session_factory() as db:
        assets = list(
            (
                await db.scalars(
                    select(MockMediaAsset)
                    .where(MockMediaAsset.chunk_index >= 0)
                    .order_by(MockMediaAsset.interview_id, MockMediaAsset.chunk_index)
                )
            ).all()
        )
        by_interview: dict[object, list[MockMediaAsset]] = defaultdict(list)
        for asset in assets:
            by_interview[asset.interview_id].append(asset)

        for interview_id, chunks in by_interview.items():
            indices = [chunk.chunk_index for chunk in chunks]
            contiguous = indices == list(range(len(chunks)))
            present = await asyncio.gather(
                *(storage.object_exists(chunk.storage_key) for chunk in chunks)
            )
            if not contiguous or not all(present):
                skipped += 1
                missing = len(chunks) - sum(present)
                reason = (
                    "non-contiguous chunk indexes"
                    if not contiguous
                    else f"{missing} missing object(s)"
                )
                print(
                    f"Skipped {interview_id}: {reason}.",
                    flush=True,
                )
                continue
            changed = [chunk for chunk in chunks if not chunk.ready]
            for chunk in changed:
                chunk.ready = True
            if changed:
                repaired += 1
                print(
                    f"Marked {len(changed)} verified chunk(s) ready for {interview_id}",
                    flush=True,
                )
        await db.commit()
    return repaired, skipped


async def main(repair_ready: bool = False) -> None:
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg is required to reprocess recordings")
    if repair_ready:
        repaired, skipped = await repair_ready_assets()
        print(f"Repaired: {repaired}; skipped: {skipped}", flush=True)
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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repair-ready",
        action="store_true",
        help="Verify stored chunks and mark complete old recordings ready before combining them.",
    )
    args = parser.parse_args()
    asyncio.run(main(repair_ready=args.repair_ready))
