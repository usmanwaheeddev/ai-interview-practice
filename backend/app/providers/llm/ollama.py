import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import Settings
from app.providers.resilience import CircuitBreaker, call_with_resilience
from app.services.json_parsing import parse_json_loosely


class OllamaLLMProvider:
    """Local, self-hosted, no API key — see memory.md ADR-014. Talks to the
    `ollama` container's HTTP API (default port 11434)."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.ollama_url
        self._model = settings.ollama_model
        # Must be >= the largest timeout_s any caller passes to complete()
        # below (extract_json's 120s) — httpx would otherwise cut the
        # request off at this client-level timeout before call_with_resilience's
        # own timeout ever gets a chance to.
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=150.0)
        self._breaker = CircuitBreaker()

    async def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 60,
        timeout_s: float = 20.0,
        max_retries: int = 2,
    ) -> str:
        async def _call() -> str:
            response = await self._client.post(
                "/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    # An interview follow-up question is a sentence, not an
                    # essay — capping generation length is a direct latency
                    # lever for token-by-token decoding. See plan.md §5's
                    # remediation list ("shorten Director outputs").
                    "options": {"num_predict": max_tokens},
                    # Belt-and-suspenders alongside the `ollama` container's
                    # OLLAMA_KEEP_ALIVE=-1: keep the model resident so a
                    # request never pays the ~90s cold-load cost on this
                    # CPU-only host, which otherwise blows well past the
                    # timeout below.
                    "keep_alive": -1,
                },
            )
            response.raise_for_status()
            body = response.json()
            content: str = body["message"]["content"]
            return content

        return await call_with_resilience(
            _call,
            provider="ollama",
            operation="complete",
            timeout_s=timeout_s,
            max_retries=max_retries,
            breaker=self._breaker,
        )

    async def stream_complete(
        self, *, system: str, user: str, max_tokens: int = 500
    ) -> AsyncIterator[str]:
        # See groq.py's stream_complete for why this skips call_with_resilience.
        if self._breaker.is_open:
            from app.providers.resilience import CircuitOpenError

            raise CircuitOpenError("ollama.stream_complete: circuit open")

        try:
            async with self._client.stream(
                "POST",
                "/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": True,
                    "options": {"num_predict": max_tokens},
                    "keep_alive": -1,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    body = json.loads(line)
                    delta = body.get("message", {}).get("content")
                    if delta:
                        yield delta
                    if body.get("done"):
                        break
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
        # Structured extraction (resume fields, plan probes) needs far more
        # room than a one-sentence interview follow-up — the 60-token
        # default on `complete` would truncate it mid-object.
        #
        # These prompts also run to 1000+ tokens (resume + job description),
        # and on this CPU-only host prompt-eval alone can take well over the
        # 20s `complete()` uses for short follow-ups — observed timing out
        # at 20s three times in a row despite a warm model (~26 tok/s eval
        # speed against a ~1800-token prompt needs ~70s+ just to read it).
        # A single generous attempt beats three retries here: retrying a
        # sustained-slowness failure doesn't help, and each retry throws
        # away the previous attempt's partial KV-cache progress.
        async def _call() -> str:
            response = await self._client.post(
                "/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {
                            "role": "system",
                            "content": prompt + " Respond with ONLY a JSON object, no other text.",
                        },
                        {"role": "user", "content": text},
                    ],
                    "stream": False,
                    # Native Ollama structured-output mode prevents the
                    # fallback model from returning prose that parses as an
                    # empty object and later fails plan/scoring validation.
                    "format": json_schema or "json",
                    "options": {"num_predict": 650},
                    "keep_alive": -1,
                },
            )
            response.raise_for_status()
            body = response.json()
            content: str = body["message"]["content"]
            return content

        raw = await call_with_resilience(
            _call,
            provider="ollama",
            operation="extract_json",
            timeout_s=120.0,
            max_retries=0,
            breaker=self._breaker,
        )
        return parse_json_loosely(raw)

    async def health(self) -> bool:
        try:
            response = await self._client.get("/api/tags", timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False
