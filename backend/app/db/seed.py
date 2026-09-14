"""Idempotent development seed for a mock-interview user.

Run via `make seed`. Safe to run repeatedly — looks up by unique fields
before inserting.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.models import CodingHintConfig, CodingQuestion, CodingTestCase, User
from app.db.seed_data.coding_questions import CODING_QUESTIONS
from app.db.session import async_session_factory
from app.services.coding.signature import validate_function_signature

configure_logging(debug=True)
logger = get_logger(__name__)

DEMO_CANDIDATE_EMAIL = "candidate@example.com"
DEMO_PASSWORD = "devpassword123"


async def seed_coding_questions(db: AsyncSession) -> None:
    for definition in CODING_QUESTIONS:
        existing = await db.scalar(
            select(CodingQuestion).where(CodingQuestion.slug == definition["slug"])
        )
        if existing is not None:
            logger.info("seed.coding_question_exists", slug=definition["slug"])
            continue

        validate_function_signature(definition["function_signature"])

        question = CodingQuestion(
            slug=definition["slug"],
            title=definition["title"],
            difficulty=definition["difficulty"],
            description=definition["description"],
            constraints=definition["constraints"],
            examples=definition["examples"],
            class_name=definition["class_name"],
            function_signature=definition["function_signature"],
            starter_code=definition["starter_code"],
        )
        db.add(question)
        await db.flush()  # assigns question.id for the test cases' FK below

        order = 0
        for is_sample, cases in (
            (True, definition["test_cases"]["sample"]),
            (False, definition["test_cases"]["hidden"]),
        ):
            for args, expected_output in cases:
                db.add(
                    CodingTestCase(
                        question_id=question.id,
                        args=args,
                        expected_output=expected_output,
                        is_sample=is_sample,
                        order=order,
                    )
                )
                order += 1

        logger.info("seed.coding_question_created", slug=definition["slug"])


async def seed_coding_hint_config(db: AsyncSession) -> None:
    existing = await db.scalar(select(CodingHintConfig).limit(1))
    if existing is not None:
        logger.info(
            "seed.coding_hint_config_exists", default_hint_limit=existing.default_hint_limit
        )
        return
    db.add(CodingHintConfig())
    logger.info("seed.coding_hint_config_created")


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

        await seed_coding_questions(db)
        await seed_coding_hint_config(db)

        await db.commit()

    logger.info(
        "seed.done",
        login=f"{DEMO_CANDIDATE_EMAIL} / {DEMO_PASSWORD}",
    )


if __name__ == "__main__":
    asyncio.run(seed())
