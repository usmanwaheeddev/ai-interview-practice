from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """A plain (non-yield) dependency for code that needs to open its own
    session *later*, on its own schedule — e.g. a StreamingResponse
    generator, which FastAPI resumes only after the route function has
    already returned and closed any yield-based `Depends(get_db)` session.
    Because this dependency has no cleanup step, it isn't subject to that
    same early-close timing; callers just call the returned factory
    whenever they actually need a session. Overridden in tests to point at
    the test database's factory — see tests/conftest.py."""
    return async_session_factory
