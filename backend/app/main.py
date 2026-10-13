from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.gdpr import router as gdpr_router
from app.api.practice import router as practice_router
from app.api.resumes import router as resumes_router
from app.api.utils import router as utils_router
from app.core.config import get_settings
from app.core.exceptions import (
    AppError,
    app_error_handler,
    unhandled_error_handler,
)
from app.core.logging import configure_logging, get_logger
from app.core.security_headers import SecurityHeadersMiddleware
from app.db.session import engine
from app.providers.storage import get_storage_provider
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
app.include_router(gdpr_router, prefix="/api")
app.include_router(utils_router, prefix="/api")
app.include_router(interview_ws_router)
