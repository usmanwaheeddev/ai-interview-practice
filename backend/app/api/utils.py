import asyncio

from fastapi import APIRouter
from sqlalchemy import text

from app.core.exceptions import ServiceUnavailableError
from app.core.redis import get_redis
from app.db.session import engine
from app.providers.llm import get_llm_provider
from app.providers.storage import get_storage_provider
from app.providers.stt import get_stt_provider
from app.providers.tts import get_tts_provider

router = APIRouter(tags=["utils"])
@router.get("health")
async def health() -> dict[str, str]:
    """Liveness — process is up. Does not touch dependencies."""
    return {"status": "ok"}


@router.get("ready")
async def ready() -> dict[str, str]:
    """Readiness — every dependency this process needs is reachable, AI
    providers included. See architecture.md §11.

    Note: for self-hosted STT/TTS the first call here is slow (model
    download + load) — that's correct, not a bug: the app genuinely isn't
    ready to serve an interview until the model is loaded. Subsequent calls
    are fast since the provider caches the loaded model."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    await get_redis().ping()

    llm, stt, tts, storage = (
        get_llm_provider(),
        get_stt_provider(),
        get_tts_provider(),
        get_storage_provider(),
    )
    llm_ok, stt_ok, tts_ok, storage_ok = await asyncio.gather(
        llm.health(), stt.health(), tts.health(), storage.health()
    )
    if not (llm_ok and stt_ok and tts_ok and storage_ok):
        raise ServiceUnavailableError(
            f"provider unhealthy: llm={llm_ok} stt={stt_ok} tts={tts_ok} storage={storage_ok}",
            code="not_ready",
        )

    return {"status": "ok", "database": "ok", "redis": "ok", "providers": "ok"}
