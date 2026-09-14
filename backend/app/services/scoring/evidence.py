"""Verify a scoring model's quoted evidence actually appears in the
transcript — memory.md ADR-006. Models fabricate fluent, plausible quotes;
a fabricated quote attributed to a candidate is the worst failure this
system can produce, so this is checked in code, never trusted from the
model's own "confidence" field."""

import re
from difflib import SequenceMatcher

VERIFICATION_THRESHOLD = 0.90


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def verify_evidence(
    quote: str, transcript: str, *, threshold: float = VERIFICATION_THRESHOLD
) -> bool:
    """True if `quote` appears in `transcript`, allowing for whitespace/case
    differences and minor paraphrasing (>=90% fuzzy ratio) — not requiring a
    byte-exact match, since normalization alone won't catch every harmless
    transcription variance."""
    norm_quote = _normalize(quote)
    norm_transcript = _normalize(transcript)

    if not norm_quote:
        return False
    if norm_quote in norm_transcript:
        return True

    if len(norm_transcript) <= len(norm_quote):
        return SequenceMatcher(None, norm_quote, norm_transcript).ratio() >= threshold

    # Slide windows across a *range* of sizes around the quote's length, not
    # just one fixed size — a single-size window can't align well once the
    # quote and transcript differ by even a couple of inserted/dropped words,
    # which is exactly the kind of harmless transcription variance this is
    # meant to tolerate.
    base = len(norm_quote)
    best = 0.0
    for window in {max(1, int(base * factor)) for factor in (0.85, 1.0, 1.15)}:
        if window > len(norm_transcript):
            window = len(norm_transcript)
        step = max(1, window // 6)
        for start in range(0, len(norm_transcript) - window + 1, step):
            segment = norm_transcript[start : start + window]
            best = max(best, SequenceMatcher(None, norm_quote, segment).ratio())
            if best >= threshold:
                return True
    return best >= threshold
