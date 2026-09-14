"""Helpers for incremental speech-to-text assembly."""

import re

_NON_WORD = re.compile(r"[^\w+#.-]+", re.UNICODE)


def is_plausible_transcript(text: str) -> bool:
    """Reject prompt-driven repetition that Whisper can emit for noise-only audio."""
    words = [_NON_WORD.sub("", word).casefold() for word in text.split()]
    words = [word for word in words if word]
    if len(words) < 8:
        return True
    counts: dict[str, int] = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    unique_ratio = len(counts) / len(words)
    most_repeated = max(counts.values(), default=0)
    return unique_ratio >= 0.35 and most_repeated <= max(4, int(len(words) * 0.3))


def merge_transcript_text(existing: str, incoming: str, *, max_overlap_words: int = 12) -> str:
    """Merge overlapping Whisper chunks without repeating boundary words."""
    left = existing.strip().split()
    right = incoming.strip().split()
    if not left:
        return " ".join(right)
    if not right:
        return " ".join(left)

    overlap = 0
    limit = min(max_overlap_words, len(left), len(right))
    left_folded = [word.casefold().strip(".,!?;:\"'") for word in left]
    right_folded = [word.casefold().strip(".,!?;:\"'") for word in right]
    for size in range(limit, 0, -1):
        if left_folded[-size:] == right_folded[:size]:
            overlap = size
            break
    return " ".join(left + right[overlap:])
