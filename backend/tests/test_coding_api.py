from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.coding import CodingDifficulty, CodingQuestion, CodingTestCase


async def _register_candidate(client: AsyncClient, email: str = "coder@example.com") -> None:
    res = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "full_name": "Coder Person"},
    )
    assert res.status_code == 201, res.text


async def _seed_question(db_session: AsyncSession) -> CodingQuestion:
    question = CodingQuestion(
        slug="two-sum",
        title="Two Sum",
        difficulty=CodingDifficulty.EASY,
        description="Return indices of the two numbers that add up to target.",
        constraints=["2 <= nums.length <= 10^4"],
        examples=[
            {"input_display": "[2,7,11,15], 9", "output_display": "[0,1]", "explanation": None}
        ],
        class_name="Solution",
        function_signature={
            "name": "twoSum",
            "params": [{"name": "nums", "type": "int[]"}, {"name": "target", "type": "int"}],
            "return_type": "int[]",
        },
        starter_code={
            "python": "class Solution:\n    def twoSum(self, nums, target):\n        pass\n",
            "java": (
                "class Solution {\n"
                "    public int[] twoSum(int[] nums, int target) { return new int[]{}; }\n"
                "}\n"
            ),
            "csharp": (
                "public class Solution {\n"
                "    public int[] twoSum(int[] nums, int target) { return new int[]{}; }\n"
                "}\n"
            ),
        },
    )
    db_session.add(question)
    await db_session.flush()
    db_session.add_all(
        [
            CodingTestCase(
                question_id=question.id, args=[[2, 7, 11, 15], 9], expected_output=[0, 1],
                is_sample=True, order=0,
            ),
            CodingTestCase(
                question_id=question.id, args=[[3, 2, 4], 6], expected_output=[1, 2],
                is_sample=False, order=1,
            ),
        ]
    )
    await db_session.commit()
    return question


async def test_list_questions_returns_summary_fields_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_question(db_session)

    res = await client.get("/api/coding-questions")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert set(body[0].keys()) == {"id", "slug", "title", "difficulty"}
    assert body[0]["slug"] == "two-sum"


async def test_get_question_detail_hides_signature_and_hidden_cases(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_question(db_session)

    res = await client.get("/api/coding-questions/two-sum")
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "Two Sum"
    assert set(body["starter_code"].keys()) == {"python", "java", "csharp"}
    assert "function_signature" not in body
    assert "test_cases" not in body


async def test_get_question_detail_404_for_unknown_slug(client: AsyncClient) -> None:
    res = await client.get("/api/coding-questions/does-not-exist")
    assert res.status_code == 404


async def test_submit_requires_auth(client: AsyncClient, db_session: AsyncSession) -> None:
    await _seed_question(db_session)

    res = await client.post(
        "/api/coding-questions/two-sum/submit", json={"language": "python", "code": "x"}
    )
    assert res.status_code == 401


async def test_submit_persists_submission_and_hides_hidden_case_details(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _register_candidate(client)
    await _seed_question(db_session)

    res = await client.post(
        "/api/coding-questions/two-sum/submit",
        json={
            "language": "python",
            "code": "class Solution:\n    def twoSum(self, nums, target):\n        return [0, 1]\n",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] in ("passed", "failed", "error")
    assert len(body["results"]) == 2

    sample_result = next(r for r in body["results"] if r["is_sample"])
    hidden_result = next(r for r in body["results"] if not r["is_sample"])
    # Sample cases may show their inputs/expected/actual; hidden ones never do.
    assert hidden_result["actual_output"] is None
    assert hidden_result["expected_output"] is None
    assert hidden_result["stderr"] is None
    assert "test_case_id" in sample_result
