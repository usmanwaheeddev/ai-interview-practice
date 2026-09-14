import json

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.coding import CodingDifficulty, CodingQuestion


def _parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.strip("\n").split("\n\n"):
        if not block:
            continue
        event_type = "message"
        data_lines = []
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_type = line[len("event: ") :]
            elif line.startswith("data: "):
                data_lines.append(line[len("data: ") :])
        events.append({"event": event_type, "data": "\n".join(data_lines)})
    return events


async def _register(client: AsyncClient, email: str = "aiuser@example.com") -> None:
    res = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "full_name": "AI User"},
    )
    assert res.status_code == 201, res.text


STARTER_CODE = "class Solution:\n    def twoSum(self, nums, target):\n        pass\n"

# At least MIN_REVIEW_AUTHORED_LINES lines beyond the python starter_code below.
CODE_WITH_ENOUGH_CONTENT = (
    "class Solution:\n"
    "    def twoSum(self, nums, target):\n"
    "        seen = {}\n"
    "        return [0, 1]\n"
)


async def _seed_question(db_session: AsyncSession) -> CodingQuestion:
    question = CodingQuestion(
        slug="two-sum",
        title="Two Sum",
        difficulty=CodingDifficulty.EASY,
        description="Return indices of the two numbers that add up to target.",
        constraints=["2 <= nums.length <= 10^4"],
        examples=[],
        class_name="Solution",
        function_signature={
            "name": "twoSum",
            "params": [{"name": "nums", "type": "int[]"}, {"name": "target", "type": "int"}],
            "return_type": "int[]",
        },
        starter_code={
            "python": "class Solution:\n    def twoSum(self, nums, target):\n        pass\n",
            "java": "class Solution {}",
            "csharp": "public class Solution {}",
        },
    )
    db_session.add(question)
    await db_session.commit()
    return question


async def test_review_streams_and_persists_log(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _register(client)
    await _seed_question(db_session)

    res = await client.post(
        "/api/coding-questions/two-sum/review",
        json={"language": "python", "code": CODE_WITH_ENOUGH_CONTENT},
    )
    assert res.status_code == 200
    events = _parse_sse(res.text)
    assert events[-1]["event"] == "done"
    done_payload = json.loads(events[-1]["data"])
    assert done_payload["contained_code"] is False

    text_chunks = "".join(e["data"] for e in events if e["event"] == "message")
    assert "fake streamed completion" in text_chunks


async def test_review_skips_llm_when_code_matches_starter(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    await _register(client)
    await _seed_question(db_session)

    calls = 0

    async def _fake_stream(*, system, user, max_tokens=500):
        nonlocal calls
        calls += 1
        yield "should not be called"

    import app.api.coding as coding_api

    monkeypatch.setattr(coding_api, "stream_complete_with_fallback", _fake_stream)

    res = await client.post(
        "/api/coding-questions/two-sum/review",
        json={"language": "python", "code": STARTER_CODE},
    )
    assert res.status_code == 200
    events = _parse_sse(res.text)
    text_chunks = "".join(e["data"] for e in events if e["event"] == "message")
    assert "write" in text_chunks.lower()
    assert calls == 0


async def test_review_skips_llm_when_below_minimum_authored_lines(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    await _register(client)
    await _seed_question(db_session)

    calls = 0

    async def _fake_stream(*, system, user, max_tokens=500):
        nonlocal calls
        calls += 1
        yield "should not be called"

    import app.api.coding as coding_api

    monkeypatch.setattr(coding_api, "stream_complete_with_fallback", _fake_stream)

    # Only one authored line ("return [0, 1]") beyond the starter skeleton —
    # below MIN_REVIEW_AUTHORED_LINES (2).
    res = await client.post(
        "/api/coding-questions/two-sum/review",
        json={
            "language": "python",
            "code": "class Solution:\n    def twoSum(self, nums, target):\n        return [0, 1]\n",
        },
    )
    assert res.status_code == 200
    events = _parse_sse(res.text)
    text_chunks = "".join(e["data"] for e in events if e["event"] == "message")
    assert "write" in text_chunks.lower()
    assert calls == 0


async def test_review_flags_contained_code(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    await _register(client)
    await _seed_question(db_session)

    async def _fake_stream(*, system, user, max_tokens=500):
        yield "Looks decent but here's a fix:\n```python\nreturn 1\n```"

    import app.api.coding as coding_api

    monkeypatch.setattr(coding_api, "stream_complete_with_fallback", _fake_stream)

    res = await client.post(
        "/api/coding-questions/two-sum/review",
        json={"language": "python", "code": CODE_WITH_ENOUGH_CONTENT},
    )
    events = _parse_sse(res.text)
    done_payload = json.loads(events[-1]["data"])
    assert done_payload["contained_code"] is True
    # Defensive pass-through: the code fence is NOT stripped, just flagged.
    assert "```" in "".join(e["data"] for e in events if e["event"] == "message")


async def test_hint_truncates_at_first_newline(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    await _register(client)
    await _seed_question(db_session)

    async def _fake_stream(*, system, user, max_tokens=500):
        yield "return "
        yield "result\nexplanation the model wasn't supposed to add"

    import app.api.coding as coding_api

    monkeypatch.setattr(coding_api, "stream_complete_with_fallback", _fake_stream)

    res = await client.post(
        "/api/coding-questions/two-sum/hint",
        json={"language": "python", "code": "class Solution:\n    pass\n", "cursor_line": 1},
    )
    assert res.status_code == 200
    events = _parse_sse(res.text)
    text_chunks = "".join(e["data"] for e in events if e["event"] == "message")
    assert text_chunks == "return result"
    assert "explanation" not in text_chunks

    done_payload = json.loads(events[-1]["data"])
    assert done_payload == {"hints_used": 1, "hint_limit": 2}


async def test_hint_limit_enforced_without_calling_llm(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    await _register(client)
    await _seed_question(db_session)

    calls = 0

    async def _fake_stream(*, system, user, max_tokens=500):
        nonlocal calls
        calls += 1
        yield "hint line"

    import app.api.coding as coding_api

    monkeypatch.setattr(coding_api, "stream_complete_with_fallback", _fake_stream)

    body = {"language": "python", "code": "pass", "cursor_line": 1}
    for _ in range(2):
        res = await client.post("/api/coding-questions/two-sum/hint", json=body)
        assert res.status_code == 200

    assert calls == 2

    res = await client.post("/api/coding-questions/two-sum/hint", json=body)
    assert res.status_code == 429
    assert res.json()["code"] == "hint_limit_reached"
    assert calls == 2  # the LLM was never called for the rejected request


async def test_ai_usage_is_self_scoped(
    client_factory, db_session: AsyncSession, monkeypatch
) -> None:
    await _seed_question(db_session)

    async def _fake_stream(*, system, user, max_tokens=500):
        yield "hint line"

    import app.api.coding as coding_api

    monkeypatch.setattr(coding_api, "stream_complete_with_fallback", _fake_stream)

    candidate_a = await client_factory()
    candidate_b = await client_factory()
    await _register(candidate_a, "a@example.com")
    await _register(candidate_b, "b@example.com")

    await candidate_a.post(
        "/api/coding-questions/two-sum/hint",
        json={"language": "python", "code": "pass", "cursor_line": 1},
    )

    res_a = await candidate_a.get("/api/coding-questions/two-sum/ai-usage")
    assert res_a.status_code == 200
    body_a = res_a.json()
    assert body_a["hints_used"] == 1
    assert body_a["hint_limit"] == 2
    assert len(body_a["hints"]) == 1
    assert body_a["hints"][0]["hint_line"] == "hint line"

    res_b = await candidate_b.get("/api/coding-questions/two-sum/ai-usage")
    assert res_b.status_code == 200
    body_b = res_b.json()
    assert body_b["hints_used"] == 0
    assert body_b["hints"] == []
