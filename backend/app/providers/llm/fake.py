import json
import re
from collections.abc import AsyncIterator
from typing import Any

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
_SECTION_RE = re.compile(r"^(skills|experience|education)\s*:?\s*$", re.IGNORECASE)
_SCORING_TASK_MARKER = "SCORING_TASK_V1"
_CANDIDATE_LINE_RE = re.compile(r"^You: (.+)$", re.MULTILINE)


class FakeLLMProvider:
    """Deterministic, non-LLM heuristic extraction — no vendor call, no cost,
    no data leaves the machine. Used in tests and as the default until a real
    provider is configured (see ADR-004: no real candidate data on free tiers
    that train on input — this is what keeps dev/demo genuinely zero-risk).

    Expects resumes with simple "Section:" headers, one item per line — good
    enough to prove the pipeline; real extraction quality arrives with a real
    LLMProvider adapter in Phase 2's provider work."""

    async def extract_json(
        self,
        *,
        prompt: str,
        text: str,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if _SCORING_TASK_MARKER in prompt:
            return json.loads(self._fake_score(prompt))
        if "Create ONE" in prompt and "primary_question" in prompt:
            return {
                "primary_question": "Tell me about a relevant project and the trade-offs you made.",
                "follow_up_hints": [
                    "your specific contribution",
                    "the trade-offs you considered",
                    "what you would improve",
                ],
                "_provider": "fake",
            }
        lines = [line.strip() for line in text.splitlines()]

        email_match = _EMAIL_RE.search(text)
        phone_match = _PHONE_RE.search(text)

        sections: dict[str, list[str]] = {"skills": [], "experience": [], "education": []}
        current: str | None = None
        for line in lines:
            header = _SECTION_RE.match(line)
            if header:
                current = header.group(1).lower()
                continue
            if current and line:
                sections[current].append(line)

        return {
            "email": email_match.group(0) if email_match else None,
            "phone": phone_match.group(0) if phone_match else None,
            "skills": sections["skills"],
            "experience": sections["experience"],
            "education": sections["education"],
        }

    async def complete(self, *, system: str, user: str, max_tokens: int = 60) -> str:
        if _SCORING_TASK_MARKER in system:
            return self._fake_score(system)
        return f"[fake completion for: {user[:60]}]"

    def _fake_score(self, system: str) -> str:
        """Deterministic stand-in for `app/services/scoring/scorer.py`'s
        per-competency call — see memory.md ADR-020. Picks a real candidate
        line out of the transcript embedded in `system` so evidence
        verification (a substring/fuzzy check against that same transcript)
        passes reliably, the same way a real model's evidence would."""
        match = _CANDIDATE_LINE_RE.search(system)
        quote = match.group(1).strip() if match else "the candidate's answer"
        return json.dumps(
            {
                "value": 3,
                "reasoning": "Deterministic fake score for testing — see FakeLLMProvider.",
                "evidence": [quote],
                "confidence": "medium",
            }
        )

    async def stream_complete(
        self, *, system: str, user: str, max_tokens: int = 500
    ) -> AsyncIterator[str]:
        # Deterministic, chunked so callers exercise real incremental
        # consumption (SSE framing, progressive Monaco inserts) without a
        # real vendor call — same spirit as `complete`'s canned response.
        for chunk in f"[fake streamed completion for: {user[:60]}]".split(" "):
            yield chunk + " "

    async def health(self) -> bool:
        return True
