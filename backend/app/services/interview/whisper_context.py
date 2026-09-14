"""Build bounded Whisper vocabulary context from already-parsed resume data."""

import re
from collections.abc import Iterable, Mapping
from typing import Any

MAX_HOTWORDS = 60
MAX_HOTWORDS_CHARACTERS = 600
_SPLIT_TERMS = re.compile(r"[,;|•\n]+")
_TECHNICAL_TOKEN = re.compile(r"\b(?:[A-Z][A-Z0-9]{1,}|[A-Za-z][A-Za-z0-9.+#-]{3,})\b")
_CONTEXT_STOPWORDS = {
    "about",
    "after",
    "before",
    "build",
    "candidate",
    "could",
    "describe",
    "design",
    "explain",
    "from",
    "have",
    "into",
    "interview",
    "large",
    "more",
    "question",
    "should",
    "technical",
    "that",
    "their",
    "these",
    "this",
    "through",
    "using",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
}
_USEFUL_FIELDS = {
    "skills",
    "technologies",
    "tools",
    "frameworks",
    "languages",
    "employer",
    "company",
    "organization",
    "title",
    "role",
    "degree",
    "institution",
}
_CONTAINER_FIELDS = {"experience", "work_experience", "employment", "education"}


def _terms(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        for term in _SPLIT_TERMS.split(value):
            cleaned = " ".join(term.split()).strip(" .:-")
            if cleaned and len(cleaned) <= 80 and len(cleaned.split()) <= 8:
                yield cleaned
    elif isinstance(value, list):
        for item in value:
            yield from _terms(item)
    elif isinstance(value, Mapping):
        for key, item in value.items():
            normalized_key = str(key).casefold()
            if normalized_key in _USEFUL_FIELDS or normalized_key in _CONTAINER_FIELDS:
                yield from _terms(item)


def _context_terms(text: str) -> Iterable[str]:
    """Extract bounded vocabulary hints, not sentences, from trusted interview context."""
    for match in _TECHNICAL_TOKEN.finditer(text):
        term = match.group(0)
        if term.casefold() not in _CONTEXT_STOPWORDS:
            yield term


def build_whisper_hotwords(
    candidate_name: str,
    parsed_resume: Mapping[str, Any],
    *context: str,
) -> str:
    """Return deduplicated name/resume/interview terms suitable for Faster-Whisper."""
    candidates = [candidate_name, *_terms(parsed_resume)]
    for text in context:
        candidates.extend(_context_terms(text))
    selected: list[str] = []
    seen: set[str] = set()
    length = 0
    for term in candidates:
        normalized = term.casefold()
        if not term or normalized in seen:
            continue
        added_length = len(term) + (2 if selected else 0)
        if len(selected) >= MAX_HOTWORDS or length + added_length > MAX_HOTWORDS_CHARACTERS:
            break
        selected.append(term)
        seen.add(normalized)
        length += added_length
    return ", ".join(selected)


def build_whisper_initial_prompt(hotwords: str, previous_text: str = "") -> str | None:
    """Combine stable vocabulary with recent streaming context."""
    parts: list[str] = []
    if hotwords:
        parts.append(f"Expected names and technical terms: {hotwords}.")
    recent_words = previous_text.split()[-50:]
    if recent_words:
        parts.append(f"Previous transcript: {' '.join(recent_words)}")
    return " ".join(parts) or None
