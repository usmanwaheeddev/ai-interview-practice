"""Idempotent development seed for a mock-interview user."""

import asyncio

from sqlalchemy import select

from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.models import User
from app.db.session import async_session_factory

configure_logging(debug=True)
logger = get_logger(__name__)

DEMO_CANDIDATE_EMAIL = "candidate@example.com"
DEMO_PASSWORD = "devpassword123"


async def seed() -> None:
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.email == DEMO_CANDIDATE_EMAIL))
        if result.scalar_one_or_none() is None:
            db.add(
                User(
                    email=DEMO_CANDIDATE_EMAIL,
                    password_hash=hash_password(DEMO_PASSWORD),
                    full_name="Casey Candidate",
                )
            )
            logger.info("seed.candidate_user_created", email=DEMO_CANDIDATE_EMAIL)
        else:
            logger.info("seed.candidate_user_exists", email=DEMO_CANDIDATE_EMAIL)
        await db.commit()

    logger.info("seed.done", login=f"{DEMO_CANDIDATE_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed())
