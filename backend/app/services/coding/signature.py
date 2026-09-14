"""Function-signature validation and per-language type mapping for the
coding-challenge execution engine. Kept intentionally small per the product
spec — extend `SUPPORTED_TYPES` (and the per-language maps below) together
when a new type is needed."""

SUPPORTED_TYPES = {"int", "float", "string", "bool", "int[]", "string[]", "float[]"}

JAVA_TYPE_MAP = {
    "int": "int",
    "float": "double",
    "string": "String",
    "bool": "boolean",
    "int[]": "int[]",
    "string[]": "String[]",
    "float[]": "double[]",
}

CSHARP_TYPE_MAP = {
    "int": "int",
    "float": "double",
    "string": "string",
    "bool": "bool",
    "int[]": "int[]",
    "string[]": "string[]",
    "float[]": "double[]",
}


class UnsupportedTypeError(ValueError):
    pass


def validate_function_signature(signature: dict) -> None:
    """Raises UnsupportedTypeError for any param/return type outside
    SUPPORTED_TYPES, rather than failing silently at harness-generation time.
    Called at seed time (see app/db/seed_data/coding_questions.py) — the
    function_signature column isn't end-user input in Phase 1."""
    name = signature.get("name")
    if not isinstance(name, str) or not name:
        raise UnsupportedTypeError("function_signature.name must be a non-empty string")

    params = signature.get("params")
    if not isinstance(params, list):
        raise UnsupportedTypeError("function_signature.params must be a list")
    for param in params:
        param_type = param.get("type")
        if param_type not in SUPPORTED_TYPES:
            raise UnsupportedTypeError(
                f"Unsupported param type '{param_type}' for '{param.get('name')}'. "
                f"Supported types: {sorted(SUPPORTED_TYPES)}"
            )

    return_type = signature.get("return_type")
    if return_type not in SUPPORTED_TYPES:
        raise UnsupportedTypeError(
            f"Unsupported return_type '{return_type}'. Supported types: {sorted(SUPPORTED_TYPES)}"
        )
