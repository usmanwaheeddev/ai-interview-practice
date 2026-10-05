"""DeepSeek's OpenAI-compatible chat-completions provider."""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import Settings
from app.providers.llm.fast_decision import (
    FAST_DECISION_MAX_TOKENS,
    FAST_DECISION_SCHEMA,
    FAST_DECISION_TIMEOUT_S,
)
from app.providers.resilience import CircuitBreaker, call_with_resilience
from app.services.json_parsing import parse_json_loosely, validate_json_result

DEEPSEEK_STRUCTURED_READ_TIMEOUT_S = 40.0
DEEPSEEK_STRUCTURED_OPERATION_TIMEOUT_S = 45.0
DEEPSEEK_STRUCTURED_MAX_TOKENS = 2_048


class DeepSeekLLMProvider:
    """Official DeepSeek API access in low-latency, non-thinking mode."""

    def __init__(self, settings: Settings) -> None:
        if not settings.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is required when LLM_PROVIDER=deepseek")

        self._model = settings.deepseek_model
        self._client = httpx.AsyncClient(
            base_url="https://api.deepseek.com",
            timeout=httpx.Timeout(
                connect=10.0,
                read=DEEPSEEK_STRUCTURED_READ_TIMEOUT_S,
                write=30.0,
                pool=10.0,
            ),
            headers={
                "Authorization": f"Bearer {settings.deepseek_api_key}",
                "Content-Type": "application/json",
            },
        )
        self._breaker = CircuitBreaker()

    @staticmethod
    def _messages(*, system: str, user: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    @staticmethod
    def _content(body: dict[str, Any]) -> str:
        choices = body.get("choices") or []
        if not choices:
            error = body.get("error") or {}
            raise ValueError(error.get("message") or "DeepSeek returned no choices")
        content = choices[0].get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("DeepSeek returned an empty response")
        return content

    def _request(self, *, system: str, user: str, max_tokens: int) -> dict[str, Any]:
        return {
            "model": self._model,
            "messages": self._messages(system=system, user=user),
            "max_tokens": max_tokens,
            "thinking": {"type": "disabled"},
        }

    async def complete(self, *, system: str, user: str, max_tokens: int = 60) -> str:
        async def _call() -> str:
            response = await self._client.post(
                "/chat/completions",
                json=self._request(system=system, user=user, max_tokens=max_tokens),
            )
            response.raise_for_status()
            return self._content(response.json())

        return await call_with_resilience(
            _call,
            provider="deepseek",
            operation="complete",
            timeout_s=20.0,
            breaker=self._breaker,
        )

    async def fast_decide(self, *, system: str, user: str) -> dict[str, Any]:
        async def _call() -> dict[str, Any]:
            payload = self._request(
                system=system + " Respond with ONLY a JSON object, no other text.",
                user=user,
                max_tokens=FAST_DECISION_MAX_TOKENS,
            )
            payload.update(
                temperature=0,
                response_format={"type": "json_object"},
            )
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            return validate_json_result(
                parse_json_loosely(self._content(response.json())),
                FAST_DECISION_SCHEMA,
                provider="DeepSeek",
            )

        return await call_with_resilience(
            _call,
            provider="deepseek",
            operation="fast_decide",
            timeout_s=FAST_DECISION_TIMEOUT_S,
            max_retries=0,
            breaker=self._breaker,
        )

    async def extract_json(
        self,
        *,
        prompt: str,
        text: str,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        schema_instruction = ""
        if json_schema:
            compact_schema = json.dumps(json_schema, ensure_ascii=False, separators=(",", ":"))
            schema_instruction = (
                " The response must conform to this exact JSON Schema: " + compact_schema
            )

        async def _call() -> dict[str, Any]:
            payload = self._request(
                system=(
                    prompt
                    + " Respond with ONLY a complete JSON object, no other text."
                    + schema_instruction
                ),
                user=text,
                max_tokens=DEEPSEEK_STRUCTURED_MAX_TOKENS,
            )
            payload["response_format"] = {"type": "json_object"}
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            parsed = parse_json_loosely(self._content(response.json()))
            return validate_json_result(parsed, json_schema, provider="DeepSeek")

        return await call_with_resilience(
            _call,
            provider="deepseek",
            operation="extract_json",
            timeout_s=DEEPSEEK_STRUCTURED_OPERATION_TIMEOUT_S,
            max_retries=0,
            breaker=self._breaker,
        )

    async def stream_complete(
        self, *, system: str, user: str, max_tokens: int = 500
    ) -> AsyncIterator[str]:
        if self._breaker.is_open:
            from app.providers.resilience import CircuitOpenError

            raise CircuitOpenError("deepseek.stream_complete: circuit open")

        payload = self._request(system=system, user=user, max_tokens=max_tokens)
        payload["stream"] = True
        try:
            async with self._client.stream(
                "POST", "/chat/completions", json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    delta = json.loads(data).get("choices", [{}])[0].get("delta", {}).get(
                        "content"
                    )
                    if delta:
                        yield delta
        except Exception:
            self._breaker.record_failure()
            raise
        else:
            self._breaker.record_success()

    async def health(self) -> bool:
        try:
            response = await self._client.get("/models", timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False
