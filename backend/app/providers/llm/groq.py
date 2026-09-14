import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import Settings
from app.providers.resilience import CircuitBreaker, call_with_resilience
from app.services.json_parsing import parse_json_loosely


class GroqLLMProvider:
    """Cloud, free-tier, OpenAI-compatible chat completions API. Groq serves
    open models on its own LPU inference hardware — chosen specifically to
    fix Phase 2's gate failure, which was CPU-only Ollama in Docker Desktop's
    Linux VM having no GPU access on this Mac (memory.md ADR-015). Requires
    `GROQ_API_KEY` (free at console.groq.com); nothing else about the
    interview engine changes — this is a config + adapter swap per the
    provider rule in CLAUDE.md."""

    def __init__(self, settings: Settings) -> None:
        self._model = settings.groq_model
        self._client = httpx.AsyncClient(
            base_url="https://api.groq.com/openai/v1",
            timeout=30.0,
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
        )
        self._breaker = CircuitBreaker()

    async def complete(self, *, system: str, user: str, max_tokens: int = 60) -> str:
        async def _call() -> str:
            response = await self._client.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            body = response.json()
            content: str = body["choices"][0]["message"]["content"]
            return content

        return await call_with_resilience(
            _call,
            provider="groq",
            operation="complete",
            timeout_s=20.0,
            breaker=self._breaker,
        )

    async def stream_complete(
        self, *, system: str, user: str, max_tokens: int = 500
    ) -> AsyncIterator[str]:
        # No call_with_resilience here deliberately — a stream can't be
        # transparently retried once chunks have already reached the
        # caller (see app/providers/llm/__init__.py's fallback wrapper,
        # which is what actually handles a failure-before-first-chunk by
        # switching providers). The circuit breaker still records outcomes
        # so a persistently down Groq stops being tried at all.
        if self._breaker.is_open:
            from app.providers.resilience import CircuitOpenError

            raise CircuitOpenError("groq.stream_complete: circuit open")

        try:
            async with self._client.stream(
                "POST",
                "/chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": max_tokens,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[len("data: ") :]
                    if payload == "[DONE]":
                        break
                    delta = json.loads(payload)["choices"][0]["delta"].get("content")
                    if delta:
                        yield delta
        except Exception:
            self._breaker.record_failure()
            raise
        else:
            self._breaker.record_success()

    async def extract_json(
        self,
        *,
        prompt: str,
        text: str,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async def _call() -> str:
            response = await self._client.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {
                            "role": "system",
                            "content": prompt + " Respond with ONLY a JSON object, no other text.",
                        },
                        {"role": "user", "content": text},
                    ],
                    "max_tokens": 650,
                    "response_format": (
                        {
                            "type": "json_schema",
                            "json_schema": {
                                "name": "extracted_data",
                                "strict": False,
                                "schema": json_schema,
                            },
                        }
                        if json_schema
                        else {"type": "json_object"}
                    ),
                },
            )
            response.raise_for_status()
            body = response.json()
            content: str = body["choices"][0]["message"]["content"]
            return content

        raw = await call_with_resilience(
            _call,
            provider="groq",
            operation="extract_json",
            timeout_s=25.0,
            # A 429 is an active quota/rate-limit decision. Repeating the
            # same structured request immediately cannot repair it and only
            # delays the configured Ollama handoff.
            max_retries=0,
            breaker=self._breaker,
        )
        return parse_json_loosely(raw)

    async def health(self) -> bool:
        try:
            response = await self._client.get("/models", timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False
