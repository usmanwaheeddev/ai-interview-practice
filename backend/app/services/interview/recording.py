"""Build a single playable recording from resilient browser-upload chunks."""

import asyncio
import shutil
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MockMediaAsset
from app.providers.storage.base import StorageProvider

MASTER_CHUNK_INDEX = -1


async def create_master_recording(
    db: AsyncSession, storage: StorageProvider, interview_id: object
) -> bool:
    """Remux ready chunks into a report-ready asset; retain chunks for recovery."""
    assets = list(
        (
            await db.scalars(
                select(MockMediaAsset)
                .where(
                    MockMediaAsset.interview_id == interview_id,
                    MockMediaAsset.ready.is_(True),
                    MockMediaAsset.chunk_index >= 0,
                )
                .order_by(MockMediaAsset.chunk_index)
            )
        ).all()
    )
    if not assets:
        return False
    kind = assets[0].kind
    if any(asset.kind != kind for asset in assets):
        raise ValueError("Recording chunks have inconsistent media kinds")

    with tempfile.TemporaryDirectory(prefix="ai-interview-recording-") as directory:
        workdir = Path(directory)
        concat_file = workdir / "chunks.txt"
        inputs: list[Path] = []
        for asset in assets:
            suffix = ".wav" if asset.content_type == "audio/wav" else ".webm"
            input_file = workdir / f"chunk-{asset.chunk_index:05d}{suffix}"
            input_file.write_bytes(await storage.get_object(asset.storage_key))
            inputs.append(input_file)
        concat_file.write_text(
            "".join(f"file '{path.as_posix()}'\n" for path in inputs), encoding="utf-8"
        )
        extension = "wav" if kind == "audio" else "webm"
        content_type = "audio/wav" if kind == "audio" else "video/webm"
        output = workdir / f"recording.{extension}"
        command = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file)]
        command.extend(["-c:a", "pcm_s16le"] if kind == "audio" else ["-c", "copy"])
        command.append(str(output))
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0 or not output.exists():
            detail = stderr.decode("utf-8", errors="replace")[-500:]
            raise RuntimeError(f"Could not combine recording chunks: {detail}")

        master = await db.scalar(
            select(MockMediaAsset).where(
                MockMediaAsset.interview_id == interview_id,
                MockMediaAsset.chunk_index == MASTER_CHUNK_INDEX,
            )
        )
        key = f"mock-interviews/{interview_id}/{kind}/recording.{extension}"
        await storage.put_file(key, output, content_type=content_type)
        if master is None:
            master = MockMediaAsset(
                interview_id=interview_id,
                kind=kind,
                chunk_index=MASTER_CHUNK_INDEX,
                storage_key=key,
                content_type=content_type,
                ready=True,
            )
            db.add(master)
        else:
            master.kind = kind
            master.storage_key = key
            master.content_type = content_type
            master.ready = True
        await db.commit()
    return True


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None
