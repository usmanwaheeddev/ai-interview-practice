from unittest.mock import AsyncMock

import httpx

from app.core.config import Settings
from app.providers.llm.ollama import OllamaLLMProvider


async def test_ollama_extract_json_enables_native_json_mode() -> None:
    provider = OllamaLLMProvider(Settings())
    response = httpx.Response(
        200,
        json={"message": {"content": '{"primary_question": "Tell me about Python"}'}},
        request=httpx.Request("POST", "http://localhost:11434/api/chat"),
    )
    post = AsyncMock(return_value=response)
    provider._client.post = post  # type: ignore[method-assign]

    result = await provider.extract_json(prompt="Create a question.", text="Resume text")

    assert result == {"primary_question": "Tell me about Python"}
    payload = post.await_args.kwargs["json"]
    assert payload["format"] == "json"
    assert payload["stream"] is False
    assert payload["keep_alive"] == -1


async def test_ollama_extract_json_passes_required_schema() -> None:
    provider = OllamaLLMProvider(Settings())
    response = httpx.Response(
        200,
        json={"message": {"content": '{"primary_question": "A question"}'}},
        request=httpx.Request("POST", "http://localhost:11434/api/chat"),
    )
    post = AsyncMock(return_value=response)
    provider._client.post = post  # type: ignore[method-assign]
    schema = {
        "type": "object",
        "properties": {"primary_question": {"type": "string"}},
        "required": ["primary_question"],
    }

    await provider.extract_json(prompt="Create a question.", text="Resume", json_schema=schema)

    assert post.await_args.kwargs["json"]["format"] == schema
