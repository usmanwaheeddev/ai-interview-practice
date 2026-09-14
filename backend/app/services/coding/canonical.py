"""Server-side counterpart to the hand-rolled canonical serializer each
language's generated driver prints its result in (see harness.py's
`*_SERIALIZER_SNIPPET` constants). Deliberately not JSON — matches the
generated output format exactly: numbers as-is, strings double-quoted with
`\\`/`"` escaped, booleans as `true`/`false`, arrays as `[a,b,c]` with no
nesting (Phase 1's supported types are all scalar or one level deep)."""

import math
from typing import Any

_ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


class CanonicalParseError(ValueError):
    pass


def parse_canonical(text: str) -> Any:
    value, pos = _parse(text, 0)
    pos = _skip_ws(text, pos)
    if pos != len(text):
        raise CanonicalParseError(f"Unexpected trailing content at {pos}: {text!r}")
    return value


def _skip_ws(s: str, i: int) -> int:
    while i < len(s) and s[i] in " \t\r\n":
        i += 1
    return i


def _parse(s: str, i: int) -> tuple[Any, int]:
    i = _skip_ws(s, i)
    if i >= len(s):
        raise CanonicalParseError("Unexpected end of output")

    if s[i] == "[":
        return _parse_array(s, i)
    if s[i] == '"':
        return _parse_string(s, i)
    if s[i:].startswith("true"):
        return True, i + 4
    if s[i:].startswith("false"):
        return False, i + 5
    return _parse_number(s, i)


def _parse_array(s: str, i: int) -> tuple[list, int]:
    assert s[i] == "["
    i = _skip_ws(s, i + 1)
    items: list[Any] = []
    if i < len(s) and s[i] == "]":
        return items, i + 1
    while True:
        value, i = _parse(s, i)
        items.append(value)
        i = _skip_ws(s, i)
        if i >= len(s):
            raise CanonicalParseError("Unterminated array")
        if s[i] == ",":
            i = _skip_ws(s, i + 1)
            continue
        if s[i] == "]":
            return items, i + 1
        raise CanonicalParseError(f"Expected ',' or ']' at {i}: {s!r}")


def _parse_string(s: str, i: int) -> tuple[str, int]:
    assert s[i] == '"'
    i += 1
    buf: list[str] = []
    while i < len(s) and s[i] != '"':
        if s[i] == "\\" and i + 1 < len(s):
            buf.append(_ESCAPES.get(s[i + 1], s[i + 1]))
            i += 2
        else:
            buf.append(s[i])
            i += 1
    if i >= len(s):
        raise CanonicalParseError("Unterminated string")
    return "".join(buf), i + 1


def _parse_number(s: str, i: int) -> tuple[int | float, int]:
    j = i
    while j < len(s) and (s[j].isdigit() or s[j] in "+-.eE"):
        j += 1
    raw = s[i:j]
    if not raw:
        raise CanonicalParseError(f"Expected a value at {i}: {s!r}")
    if any(c in raw for c in ".eE"):
        return float(raw), j
    return int(raw), j


def normalize_for_compare(value: Any, return_type: str) -> Any:
    """Reconciles trivial representation differences (e.g. `2` vs `2.0`)
    based on what the signature declares the return type to be — not what
    happened to come back."""
    if return_type == "int" and isinstance(value, float) and value.is_integer():
        return int(value)
    if return_type == "float" and isinstance(value, int):
        return float(value)
    if return_type == "int[]" and isinstance(value, list):
        return [int(v) if isinstance(v, float) and v.is_integer() else v for v in value]
    if return_type == "float[]" and isinstance(value, list):
        return [float(v) if isinstance(v, int) else v for v in value]
    return value


def outputs_match(actual: Any, expected: Any, return_type: str) -> bool:
    a = normalize_for_compare(actual, return_type)
    e = normalize_for_compare(expected, return_type)

    if return_type == "float":
        if not (isinstance(a, int | float) and isinstance(e, int | float)):
            return False
        return math.isclose(a, e, rel_tol=1e-6, abs_tol=1e-9)

    if return_type == "float[]":
        if not (isinstance(a, list) and isinstance(e, list) and len(a) == len(e)):
            return False
        return all(
            isinstance(x, int | float)
            and isinstance(y, int | float)
            and math.isclose(x, y, rel_tol=1e-6, abs_tol=1e-9)
            for x, y in zip(a, e, strict=True)
        )

    return a == e
