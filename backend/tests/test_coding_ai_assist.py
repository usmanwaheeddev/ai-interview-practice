from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models import CodingDifficulty, CodingQuestion, User
from app.db.models.coding import CodingHintConfig, CodingHintUsage
from app.services.coding.ai_assist import (
    build_hint_prompt,
    build_review_prompt,
    count_authored_lines,
    get_hint_limit,
    get_or_create_hint_usage,
)

QUESTION = type(
    "Q",
    (),
    {
        "title": "Two Sum",
        "difficulty": "easy",
        "description": "Return indices that add up to target.",
        "constraints": ["2 <= nums.length"],
        "class_name": "Solution",
        "function_signature": {
            "name": "twoSum",
            "params": [{"name": "nums", "type": "int[]"}, {"name": "target", "type": "int"}],
            "return_type": "int[]",
        },
    },
)()


def test_review_prompt_contains_question_and_code():
    prompt = build_review_prompt(QUESTION, "python", "class Solution: pass")
    assert "Two Sum" in prompt
    assert "class Solution: pass" in prompt
    assert "python" in prompt


def test_hint_prompt_includes_cursor_position():
    prompt = build_hint_prompt(QUESTION, "python", "class Solution: pass", 4, 8)
    assert "line 4, column 8" in prompt


def test_hint_prompt_without_cursor_position():
    prompt = build_hint_prompt(QUESTION, "python", "class Solution: pass", None, None)
    assert "No cursor position was given" in prompt


STARTER = "class Solution:\n    def twoSum(self, nums, target):\n        pass\n"


def test_count_authored_lines_zero_when_code_matches_starter():
    assert count_authored_lines(STARTER, STARTER) == 0


def test_count_authored_lines_ignores_boilerplate_lines():
    code = "class Solution:\n    def twoSum(self, nums, target):\n        return [0, 1]\n"
    assert count_authored_lines(STARTER, code) == 1


def test_count_authored_lines_counts_new_lines():
    code = (
        "class Solution:\n"
        "    def twoSum(self, nums, target):\n"
        "        seen = {}\n"
        "        return [0, 1]\n"
    )
    assert count_authored_lines(STARTER, code) == 2


def test_count_authored_lines_ignores_blank_lines():
    code = STARTER + "\n\n   \n"
    assert count_authored_lines(STARTER, code) == 0


async def test_get_hint_limit_lazily_creates_default_config(db_session: AsyncSession):
    limit = await get_hint_limit(db_session)
    assert limit == 2

    configs = list(await db_session.scalars(select(CodingHintConfig)))
    assert len(configs) == 1


async def test_get_or_create_hint_usage_creates_then_reuses(db_session: AsyncSession):
    user = User(
        email="hintuser@example.com", password_hash=hash_password("pw"), full_name="Hint User"
    )
    question = CodingQuestion(
        slug="test-q",
        title="Test",
        difficulty=CodingDifficulty.EASY,
        description="d",
        constraints=[],
        examples=[],
        class_name="Solution",
        function_signature={"name": "f", "params": [], "return_type": "int"},
        starter_code={"python": "", "java": "", "csharp": ""},
    )
    db_session.add_all([user, question])
    await db_session.flush()
    user_id, question_id = user.id, question.id

    usage = await get_or_create_hint_usage(db_session, user_id, question_id)
    assert usage.hints_used == 0

    usage.hints_used = 1
    await db_session.commit()

    usage_again = await get_or_create_hint_usage(db_session, user_id, question_id)
    assert usage_again.hints_used == 1

    all_usages = list(
        await db_session.scalars(
            select(CodingHintUsage).where(
                CodingHintUsage.user_id == user_id, CodingHintUsage.question_id == question_id
            )
        )
    )
    assert len(all_usages) == 1
