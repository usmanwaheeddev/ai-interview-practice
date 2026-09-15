"""Ordered primary/fallback composition for the two real LLM providers.

Wraps the full `LLMProvider` surface so every caller that
goes through `get_llm_provider()` — interview plan generation, the Director's
follow-up judging, resume extraction, and report scoring — gets the same
fallback with no per-call-site logic."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from app.providers.llm.base import LLMProvider


class FallbackLLMProvider:
    def __init__(
        self,
        primary: LLMProvider,
        fallback: LLMProvider,
        *,
        primary_name: str = "groq",
        fallback_name: str = "ollama",
        primary_json_timeout_s: float = 30.0,
        fallback_json_timeout_s: float = 150.0,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._primary_name = primary_name
        self._fallback_name = fallback_name
        self._primary_json_timeout_s = primary_json_timeout_s
        self._fallback_json_timeout_s = fallback_json_timeout_s

    async def extract_json(
        self,
        *,
        prompt: str,
        text: str,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            result = await asyncio.wait_for(
                self._primary.extract_json(
                    prompt=prompt, text=text, json_schema=json_schema
                ),
                timeout=self._primary_json_timeout_s,
            )
            return {**result, "_provider": self._primary_name}
        except Exception:
            result = await asyncio.wait_for(
                self._fallback.extract_json(
                    prompt=prompt, text=text, json_schema=json_schema
                ),
                timeout=self._fallback_json_timeout_s,
            )
            return {**result, "_provider": self._fallback_name}

    async def complete(self, *, system: str, user: str, max_tokens: int = 60) -> str:
        try:
            return await self._primary.complete(system=system, user=user, max_tokens=max_tokens)
        except Exception:
            return await self._fallback.complete(system=system, user=user, max_tokens=max_tokens)

    async def stream_complete(
        self, *, system: str, user: str, max_tokens: int = 500
    ) -> AsyncIterator[str]:
        # A failure *partway* through a stream (chunks already yielded) is
        # not retried — it propagates. Silently switching providers
        # mid-stream would produce inconsistent/duplicated output for a
        # caller that's already forwarding chunks to a client over SSE.
        started = False
        try:
            async for chunk in self._primary.stream_complete(
                system=system, user=user, max_tokens=max_tokens
            ):
                started = True
                yield chunk
            return
        except Exception:
            if started:
                raise

        async for chunk in self._fallback.stream_complete(
            system=system, user=user, max_tokens=max_tokens
        ):
            yield chunk

    async def health(self) -> bool:
        return await self._primary.health() or await self._fallback.health()
