from unittest.mock import AsyncMock

import httpx

from app.core.config import Settings
from app.providers.llm.deepseek import (
    DEEPSEEK_STRUCTURED_MAX_TOKENS,
    DEEPSEEK_STRUCTURED_READ_TIMEOUT_S,
    DeepSeekLLMProvider,
)
from app.providers.llm.fast_decision import FAST_DECISION_SCHEMA


async def test_deepseek_complete_uses_official_endpoint_in_non_thinking_mode() -> None:
    provider = DeepSeekLLMProvider(
        Settings(deepseek_api_key="test-deepseek-key", deepseek_model="deepseek-flash")
    )
    response = httpx.Response(
        200,
        json={"choices": [{"message": {"content": "hello"}}]},
        request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
    )
    post = AsyncMock(return_value=response)
    provider._client.post = post  # type: ignore[method-assign]

    assert await provider.complete(system="system", user="user") == "hello"
    request = post.await_args
    assert request.args[0] == "/chat/completions"
    assert request.kwargs["json"]["model"] == "deepseek-flash"
    assert request.kwargs["json"]["thinking"] == {"type": "disabled"}
    assert provider._client.headers["authorization"] == "Bearer test-deepseek-key"
    assert provider._client.timeout.read == DEEPSEEK_STRUCTURED_READ_TIMEOUT_S


async def test_deepseek_fast_decide_uses_json_mode_and_validates_schema() -> None:
    provider = DeepSeekLLMProvider(Settings(deepseek_api_key="test-deepseek-key"))
    response = httpx.Response(
        200,
        json={"choices": [{"message": {"content": '{"action":"advance","text":""}'}}]},
        request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
    )
    post = AsyncMock(return_value=response)
    provider._client.post = post  # type: ignore[method-assign]

    assert await provider.fast_decide(system="judge", user="answer") == {
        "action": "advance",
        "text": "",
    }
    payload = post.await_args.kwargs["json"]
    assert payload["max_tokens"] == 96
    assert payload["temperature"] == 0
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["response_format"] == {"type": "json_object"}
    assert FAST_DECISION_SCHEMA["required"] == ["action", "text"]


async def test_deepseek_extract_json_sends_schema_with_larger_output_limit() -> None:
    provider = DeepSeekLLMProvider(Settings(deepseek_api_key="test-deepseek-key"))
    response = httpx.Response(
        200,
        json={"choices": [{"message": {"content": '{"questions":[]}'}}]},
        request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
    )
    post = AsyncMock(return_value=response)
    provider._client.post = post  # type: ignore[method-assign]
    schema = {
        "type": "object",
        "properties": {"questions": {"type": "array"}},
        "required": ["questions"],
    }

    result = await provider.extract_json(
        prompt="Create questions as JSON.", text="topics", json_schema=schema
    )

    assert result == {"questions": []}
    payload = post.await_args.kwargs["json"]
    assert payload["max_tokens"] == DEEPSEEK_STRUCTURED_MAX_TOKENS
    assert '\"required\":[\"questions\"]' in payload["messages"][0]["content"]
    assert payload["response_format"] == {"type": "json_object"}


def test_deepseek_requires_api_key() -> None:
    try:
        DeepSeekLLMProvider(Settings(deepseek_api_key=""))
    except ValueError as exc:
        assert "DEEPSEEK_API_KEY" in str(exc)
    else:
        raise AssertionError("DeepSeek provider should require an API key")
