import subprocess
import sys

import pytest

from app.db.models.coding import CodingLanguage
from app.services.coding.canonical import parse_canonical
from app.services.coding.harness import (
    build_java_source,
    build_python_source,
    render_literal_csharp,
    render_literal_java,
    render_literal_python,
)


class _Question:
    def __init__(self, class_name: str, function_signature: dict):
        self.class_name = class_name
        self.function_signature = function_signature


TWO_SUM = _Question(
    "Solution",
    {
        "name": "twoSum",
        "params": [{"name": "nums", "type": "int[]"}, {"name": "target", "type": "int"}],
        "return_type": "int[]",
    },
)


@pytest.mark.parametrize(
    ("type_", "value", "expected"),
    [
        ("int", 5, "5"),
        ("string", 'he said "hi"\\', '"he said \\"hi\\"\\\\"'),
        ("bool", True, "True"),
        ("int[]", [1, 2, 3], "[1, 2, 3]"),
    ],
)
def test_render_literal_python(type_, value, expected):
    assert render_literal_python(type_, value) == expected


def test_render_literal_java_array():
    assert render_literal_java("int[]", [2, 7, 11, 15]) == "new int[]{2, 7, 11, 15}"
    assert render_literal_java("string", 'a"b') == '"a\\"b"'


def test_render_literal_csharp_array():
    assert render_literal_csharp("string[]", ["a", "b"]) == 'new string[]{"a", "b"}'


def test_build_python_source_runs_and_produces_canonical_output():
    code = (
        "class Solution:\n"
        "    def twoSum(self, nums, target):\n"
        "        seen = {}\n"
        "        for i, x in enumerate(nums):\n"
        "            if target - x in seen:\n"
        "                return [seen[target - x], i]\n"
        "            seen[x] = i\n"
    )
    source = build_python_source(TWO_SUM, code, [[2, 7, 11, 15], 9])
    compile(source, "<generated>", "exec")  # must be syntactically valid

    result = subprocess.run(
        [sys.executable, "-c", source], capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0, result.stderr
    assert parse_canonical(result.stdout.strip()) == [0, 1]


def test_build_java_source_uses_non_public_solution_and_public_main():
    code = (
        "class Solution {\n"
        "    public int[] twoSum(int[] nums, int target) { return new int[]{0, 1}; }\n"
        "}\n"
    )
    source = build_java_source(TWO_SUM, code, [[2, 7, 11, 15], 9])
    assert "class Solution {" in source
    assert "public class Solution" not in source
    assert "public class Main {" in source
    assert "new int[]{2, 7, 11, 15}" in source
    assert "new Solution().twoSum" in source


def test_build_source_dispatches_by_language():
    from app.services.coding.harness import build_source

    code = "class Solution:\n    def twoSum(self, nums, target):\n        return [0, 1]\n"
    source = build_source(CodingLanguage.PYTHON, TWO_SUM, code, [[2, 7, 11, 15], 9])
    assert "def __serialize" in source
