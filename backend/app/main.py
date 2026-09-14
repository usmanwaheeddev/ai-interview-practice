from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.auth import router as auth_router
from app.api.coding import router as coding_router
from app.api.gdpr import router as gdpr_router
from app.api.practice import router as practice_router
from app.api.provider_tests import router as provider_tests_router
from app.api.resumes import router as resumes_router
from app.core.config import get_settings
from app.core.exceptions import (
    AppError,
    ServiceUnavailableError,
    app_error_handler,
    unhandled_error_handler,
)
from app.core.logging import configure_logging, get_logger
from app.core.redis import get_redis
from app.core.security_headers import SecurityHeadersMiddleware
from app.db.session import engine
from app.providers.llm import get_llm_provider
from app.providers.storage import get_storage_provider
from app.providers.stt import get_stt_provider
from app.providers.tts import get_tts_provider
from app.ws.interview import router as interview_ws_router

settings = get_settings()
configure_logging(settings.debug)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app.startup", env=settings.env)
    if settings.storage_provider == "s3":
        from app.providers.storage.s3 import S3StorageProvider

        storage = get_storage_provider()
        assert isinstance(storage, S3StorageProvider)
        storage.ensure_bucket()
    yield
    await engine.dispose()
    logger.info("app.shutdown")


app = FastAPI(
    title="AI Mock Interviews API",
    description=(
        "Backend API for resume-aware mock interviews. Authenticate with `/api/auth/login`; "
        "the Swagger client will retain the HTTP-only session cookies for subsequent requests."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware, hsts=settings.env == "production")

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

app.include_router(auth_router, prefix="/api")
app.include_router(practice_router, prefix="/api")
app.include_router(resumes_router, prefix="/api")
app.include_router(coding_router, prefix="/api")
app.include_router(gdpr_router, prefix="/api")
app.include_router(provider_tests_router, prefix="/api")
app.include_router(interview_ws_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness — process is up. Does not touch dependencies."""
    return {"status": "ok"}


@app.get("/ready")
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
    llm_ok, stt_ok, tts_ok, storage_ok = (
        await llm.health(),
        await stt.health(),
        await tts.health(),
        await storage.health(),
    )
    if not (llm_ok and stt_ok and tts_ok and storage_ok):
        raise ServiceUnavailableError(
            f"provider unhealthy: llm={llm_ok} stt={stt_ok} tts={tts_ok} storage={storage_ok}",
            code="not_ready",
        )

    return {"status": "ok", "database": "ok", "redis": "ok", "providers": "ok"}
