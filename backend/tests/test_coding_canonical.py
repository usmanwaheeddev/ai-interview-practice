import pytest

from app.services.coding.canonical import (
    CanonicalParseError,
    outputs_match,
    parse_canonical,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("5", 5),
        ("-3", -3),
        ("2.5", 2.5),
        ("true", True),
        ("false", False),
        ('"hello"', "hello"),
        ('""', ""),
        ('"with \\"quote\\" and \\\\backslash\\\\"', 'with "quote" and \\backslash\\'),
        ("[1,2,3]", [1, 2, 3]),
        ("[]", []),
        ('["a","b"]', ["a", "b"]),
        ('[1,"a",true]', [1, "a", True]),
    ],
)
def test_parse_canonical_round_trip(text, expected):
    assert parse_canonical(text) == expected


def test_parse_canonical_rejects_trailing_garbage():
    with pytest.raises(CanonicalParseError):
        parse_canonical("5 extra")


def test_parse_canonical_rejects_unterminated_array():
    with pytest.raises(CanonicalParseError):
        parse_canonical("[1,2")


@pytest.mark.parametrize(
    ("actual", "expected", "return_type", "match"),
    [
        (2, 2.0, "int", True),
        (2.0, 2, "float", True),
        ([1, 2], [1.0, 2.0], "int[]", True),
        (2.0000001, 2.0, "float", True),
        (2.1, 2.0, "float", False),
        ("a", "b", "string", False),
        (True, True, "bool", True),
    ],
)
def test_outputs_match_normalizes_numeric_representation(actual, expected, return_type, match):
    assert outputs_match(actual, expected, return_type) is match
