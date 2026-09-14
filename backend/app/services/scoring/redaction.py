"""Transcript redaction before scoring — CLAUDE.md non-negotiable #3 /
architecture.md §6 step 1: the scoring model sees answers and the rubric,
not an identity.

**Honest scope.** There's no structured age/gender/nationality/university
field anywhere in this schema (see `db/models/user.py`, `resume.py`) — a
candidate can only reveal these by saying them out loud, so this operates on
free text with patterns, not a lookup. Name and email are redacted exactly
(sourced from the `User` row); phone/age/school/nationality are best-effort
pattern matches, not a claim of completeness. What this deliberately does
**not** attempt: stripping pronouns (he/she/they) — those routinely refer to
someone *other* than the candidate ("she reviewed my design"), and blanket
removal would corrupt legitimate answer content for a benefit that's
unreliable anyway. Versioned (`REDACTION_VERSION`) so a historical score
stays explainable against exactly what its scoring model saw — see
memory.md ADR-020.
"""

import re

REDACTION_VERSION = "v1"

_PHONE_RE = re.compile(r"\+?\d[\d\-.\s()]{7,}\d")

_AGE_RE = re.compile(
    r"\bI(?:'m| am)\s+\d{1,3}\b|\b\d{1,3}\s*(?:years?\s*old|yo)\b",
    re.IGNORECASE,
)

_SCHOOL_RE = re.compile(
    r"\bUniversity of [A-Z][\w'&-]*(?:\s+[A-Z][\w'&-]*){0,3}\b"
    r"|\b[A-Z][\w'&-]*(?:\s+[A-Z][\w'&-]*){0,3}\s+(?:University|College)\b"
)

# Not exhaustive — a representative set of self-identifying phrasing, not a
# demonym dictionary. See module docstring.
_NATIONALITY_RE = re.compile(
    r"\bI(?:'m| am)\s+(?:an?\s+)?(American|British|Canadian|Indian|Chinese|Mexican|French|"
    r"German|Nigerian|Filipino|Brazilian|Australian|Japanese|Korean|Vietnamese|Pakistani|"
    r"Egyptian|Kenyan|Irish|Polish|Ukrainian|Dutch|Spanish|Italian)\b",
    re.IGNORECASE,
)

_GENDER_SELF_RE = re.compile(
    r"\bas a (woman|man|mother|father|mom|dad)\b",
    re.IGNORECASE,
)


def redact_transcript(text: str, *, candidate_name: str, candidate_email: str) -> str:
    redacted = text

    # Email *before* name tokens: a first name that's also the email's local
    # part (e.g. "Casey" / "casey@example.com") would otherwise get name-
    # redacted first, leaving no literal email string left for the exact-match
    # replacement below to find — silently under-redacting the email.
    if candidate_email:
        redacted = redacted.replace(candidate_email, "[EMAIL]")

    for token in {t for t in candidate_name.split() if len(t) > 1}:
        redacted = re.sub(rf"\b{re.escape(token)}\b", "[NAME]", redacted, flags=re.IGNORECASE)

    redacted = _PHONE_RE.sub("[PHONE]", redacted)
    redacted = _AGE_RE.sub("[AGE]", redacted)
    redacted = _SCHOOL_RE.sub("[SCHOOL]", redacted)
    redacted = _NATIONALITY_RE.sub("[NATIONALITY]", redacted)
    redacted = _GENDER_SELF_RE.sub("[REDACTED]", redacted)
    return redacted
