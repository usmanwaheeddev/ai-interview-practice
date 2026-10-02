"""Ordered primary/fallback composition for real LLM providers.

Wraps the full `LLMProvider` surface so every caller that
goes through `get_llm_provider()` — interview plan generation, the Director's
follow-up judging, resume extraction, and report scoring — gets the same
fallback with no per-call-site logic."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from app.providers.llm.base import LLMProvider
from app.providers.llm.fast_decision import FAST_DECISION_SCHEMA
from app.services.json_parsing import validate_json_result


def _describe_error(error: Exception) -> str:
    message = str(error).strip()
    return message or type(error).__name__


class FallbackLLMProvider:
    def __init__(
        self,
        primary: LLMProvider,
        fallback: LLMProvider,
        *,
        primary_name: str = "deepseek",
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
            validate_json_result(result, json_schema, provider=self._primary_name)
            return {**result, "_provider": self._primary_name}
        except Exception as primary_error:
            try:
                result = await asyncio.wait_for(
                    self._fallback.extract_json(
                        prompt=prompt, text=text, json_schema=json_schema
                    ),
                    timeout=self._fallback_json_timeout_s,
                )
            except Exception as fallback_error:
                # Do not hide the actionable primary-provider failure behind
                # an unavailable fallback (for example, DeepSeek followed by
                # a stopped local Ollama server).
                raise RuntimeError(
                    f"{self._primary_name} failed: {_describe_error(primary_error)}; "
                    f"{self._fallback_name} failed: {_describe_error(fallback_error)}"
                ) from fallback_error
            validate_json_result(result, json_schema, provider=self._fallback_name)
            return {**result, "_provider": result.get("_provider", self._fallback_name)}

    async def complete(self, *, system: str, user: str, max_tokens: int = 60) -> str:
        try:
            return await self._primary.complete(system=system, user=user, max_tokens=max_tokens)
        except Exception:
            return await self._fallback.complete(system=system, user=user, max_tokens=max_tokens)

    async def fast_decide(self, *, system: str, user: str) -> dict[str, Any]:
        async def call(provider: LLMProvider) -> dict[str, Any]:
            method = getattr(provider, "fast_decide", None)
            if method is not None:
                return await method(system=system, user=user)
            return await provider.extract_json(
                prompt=system, text=user, json_schema=FAST_DECISION_SCHEMA
            )

        try:
            result = await asyncio.wait_for(call(self._primary), timeout=15.0)
            validate_json_result(result, FAST_DECISION_SCHEMA, provider=self._primary_name)
            return {**result, "_provider": self._primary_name}
        except Exception as primary_error:
            try:
                result = await asyncio.wait_for(call(self._fallback), timeout=15.0)
            except Exception as fallback_error:
                raise RuntimeError(
                    f"{self._primary_name} failed: {_describe_error(primary_error)}; "
                    f"{self._fallback_name} failed: {_describe_error(fallback_error)}"
                ) from fallback_error
            validate_json_result(result, FAST_DECISION_SCHEMA, provider=self._fallback_name)
            return {**result, "_provider": result.get("_provider", self._fallback_name)}

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
