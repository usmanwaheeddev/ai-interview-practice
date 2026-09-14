import pytest

from app.services.coding.signature import UnsupportedTypeError, validate_function_signature


def test_accepts_all_supported_types():
    validate_function_signature(
        {
            "name": "example",
            "params": [
                {"name": "a", "type": "int"},
                {"name": "b", "type": "float"},
                {"name": "c", "type": "string"},
                {"name": "d", "type": "bool"},
                {"name": "e", "type": "int[]"},
                {"name": "f", "type": "string[]"},
                {"name": "g", "type": "float[]"},
            ],
            "return_type": "int",
        }
    )


def test_rejects_unsupported_param_type():
    with pytest.raises(UnsupportedTypeError):
        validate_function_signature(
            {
                "name": "example",
                "params": [{"name": "a", "type": "dict"}],
                "return_type": "int",
            }
        )


def test_rejects_unsupported_return_type():
    with pytest.raises(UnsupportedTypeError):
        validate_function_signature(
            {"name": "example", "params": [], "return_type": "object"}
        )


def test_rejects_missing_name():
    with pytest.raises(UnsupportedTypeError):
        validate_function_signature({"params": [], "return_type": "int"})
