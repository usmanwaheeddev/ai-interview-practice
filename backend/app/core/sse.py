"""Minimal Server-Sent Events framing — shared by any endpoint that streams
(currently just the coding-challenge AI review/hint endpoints, see
app/api/coding.py). Not tied to any one feature's payload shape."""


def format_sse(data: str, *, event: str | None = None) -> str:
    # Per the SSE spec, each line of `data` needs its own "data: " prefix.
    lines = data.split("\n")
    payload = "".join(f"data: {line}\n" for line in lines)
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}{payload}\n"
