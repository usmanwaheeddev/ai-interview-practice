from typing import Any

from httpx import AsyncClient

from app.api.provider_tests import get_groq_test_provider
from app.core.deps import get_current_user
from app.main import app


class FakeGroqProvider:
    async def complete(self, *, system: str, user: str, max_tokens: int = 60) -> str:
        assert system == "You are a concise API connectivity test."
        assert user == "ping"
        assert max_tokens == 40
        return "pong"


async def test_swagger_is_available(client: AsyncClient) -> None:
    docs = await client.get("/docs")
    assert docs.status_code == 200
    assert "swagger-ui" in docs.text.lower()

    schema = (await client.get("/openapi.json")).json()
    assert "/api/provider-tests/groq" in schema["paths"]


async def test_groq_test_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/api/provider-tests/groq", json={"prompt": "ping"})
    assert response.status_code == 401


async def test_groq_test_returns_provider_response(client: AsyncClient) -> None:
    async def authenticated_user() -> Any:
        return object()

    app.dependency_overrides[get_current_user] = authenticated_user
    app.dependency_overrides[get_groq_test_provider] = lambda: FakeGroqProvider()
    try:
        response = await client.post("/api/provider-tests/groq", json={"prompt": "ping"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_groq_test_provider, None)

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "provider": "groq",
        "model": "qwen/qwen3.8-27b",
        "response": "pong",
    }
