import uuid

from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedError
from app.core.security import TokenType, decode_token
from app.db.models import User
from app.db.session import get_db


async def get_current_user(
    access_token: str | None = Cookie(default=None), db: AsyncSession = Depends(get_db)
) -> User:
    if not access_token:
        raise UnauthorizedError("Not authenticated", code="no_token")
    payload = decode_token(access_token, expected_type=TokenType.ACCESS)
    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None:
        raise UnauthorizedError("User no longer exists", code="user_gone")
    return user
