import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.rate_limit import enforce_rate_limit
from app.core.redis import get_redis
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()

# Browsers drop `Secure` cookies on plain-HTTP origins (e.g. the dev
# server at http://localhost:5173), which silently breaks login there.
# Non-development environments must stay HTTPS-only.
_COOKIE_SECURE = settings.env != "development"


def _set_auth_cookies(response: Response, *, user: User) -> None:
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    response.set_cookie(
        "access_token",
        access_token,
        max_age=settings.access_token_ttl_minutes * 60,
        httponly=True,
        samesite="strict",
        secure=_COOKIE_SECURE,
        path="/",
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        httponly=True,
        samesite="strict",
        secure=_COOKIE_SECURE,
        path="/",
    )


async def _email_taken(db: AsyncSession, email: str) -> bool:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none() is not None


def _client_ip(request: Request) -> str:
    # No reverse-proxy X-Forwarded-For handling — this dev stack has no
    # proxy in front of the API yet. Revisit before Phase 6's "real
    # candidate" bar if one is added, or every request will rate-limit
    # against the proxy's own IP instead of the caller's.
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=UserResponse, status_code=201)
async def register_user(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    await enforce_rate_limit(
        redis,
        key=f"register:{_client_ip(request)}",
        limit=5,
        window_s=3600,
        message="Too many registration attempts — try again in a while.",
    )
    if await _email_taken(db, body.email):
        raise ConflictError("Email already registered", code="email_taken")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    _set_auth_cookies(response, user=user)
    return user


@router.post("/login", response_model=UserResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    # Per-IP, not per-email — rate-limiting by the attempted email would let
    # an attacker sidestep the limit just by rotating target accounts, and
    # would let one attacker lock a real user out of their own login.
    await enforce_rate_limit(
        redis,
        key=f"login:{_client_ip(request)}",
        limit=10,
        window_s=300,
        message="Too many login attempts — try again in a few minutes.",
    )
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise UnauthorizedError("Invalid email or password", code="bad_credentials")

    user.last_login_at = datetime.now(UTC)
    await db.commit()

    _set_auth_cookies(response, user=user)
    return user


@router.post("/refresh", response_model=UserResponse)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
) -> User:
    if not refresh_token:
        raise UnauthorizedError("No refresh token", code="no_refresh_token")

    payload = decode_token(refresh_token, expected_type=TokenType.REFRESH)
    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None:
        raise UnauthorizedError("User no longer exists", code="user_gone")

    _set_auth_cookies(response, user=user)
    return user


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
