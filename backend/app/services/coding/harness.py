"""Literal-injection harness generation — see phases.md's coding-challenge
spec §4. The candidate's submitted `code` is the *entire* file they edited in
Monaco (it starts as `starter_code[language]`, a full class/method skeleton
with a `write your code here` placeholder, and by the time it's submitted the
candidate has replaced that placeholder in place). The harness therefore
never re-splices text into a template — it takes the submitted file as-is and
appends a small generated "driver" section per test case: literal args in
that language's own syntax, a call into `class_name`/`function_signature`,
and a hand-rolled canonical-format print (see canonical.py for the matching
parser). One call per test case (see runner.py) keeps this simple and gives
independent stderr/runtime per case.
"""

from typing import Any

from app.db.models.coding import CodingLanguage, CodingQuestion
from app.services.coding.signature import CSHARP_TYPE_MAP, JAVA_TYPE_MAP


def _escape_string(value: str, quote: str = '"') -> str:
    return value.replace("\\", "\\\\").replace(quote, "\\" + quote)


def render_literal_python(type_: str, value: Any) -> str:
    if type_ == "string":
        return '"' + _escape_string(value) + '"'
    if type_ == "bool":
        return "True" if value else "False"
    if type_ == "int":
        return str(value)
    if type_ == "float":
        return repr(float(value))
    if type_ == "int[]":
        return "[" + ", ".join(render_literal_python("int", v) for v in value) + "]"
    if type_ == "string[]":
        return "[" + ", ".join(render_literal_python("string", v) for v in value) + "]"
    if type_ == "float[]":
        return "[" + ", ".join(render_literal_python("float", v) for v in value) + "]"
    raise ValueError(f"Unsupported type for literal rendering: {type_}")


def render_literal_java(type_: str, value: Any) -> str:
    if type_ == "string":
        return '"' + _escape_string(value) + '"'
    if type_ == "bool":
        return "true" if value else "false"
    if type_ == "int":
        return str(value)
    if type_ == "float":
        return f"{float(value)}d"
    if type_ == "int[]":
        return "new int[]{" + ", ".join(render_literal_java("int", v) for v in value) + "}"
    if type_ == "string[]":
        return "new String[]{" + ", ".join(render_literal_java("string", v) for v in value) + "}"
    if type_ == "float[]":
        return "new double[]{" + ", ".join(render_literal_java("float", v) for v in value) + "}"
    raise ValueError(f"Unsupported type for literal rendering: {type_}")


def render_literal_csharp(type_: str, value: Any) -> str:
    if type_ == "string":
        return '"' + _escape_string(value) + '"'
    if type_ == "bool":
        return "true" if value else "false"
    if type_ == "int":
        return str(value)
    if type_ == "float":
        return f"{float(value)}d"
    if type_ == "int[]":
        return "new int[]{" + ", ".join(render_literal_csharp("int", v) for v in value) + "}"
    if type_ == "string[]":
        return "new string[]{" + ", ".join(render_literal_csharp("string", v) for v in value) + "}"
    if type_ == "float[]":
        return "new double[]{" + ", ".join(render_literal_csharp("float", v) for v in value) + "}"
    raise ValueError(f"Unsupported type for literal rendering: {type_}")


_PYTHON_SERIALIZER = '''

def __serialize(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return '"' + value.replace("\\\\", "\\\\\\\\").replace('"', '\\\\"') + '"'
    if isinstance(value, list):
        return "[" + ",".join(__serialize(v) for v in value) + "]"
    return repr(value) if isinstance(value, float) else str(value)
'''

_JAVA_SERIALIZER = r'''
    static String __serialize(int v) { return Integer.toString(v); }
    static String __serialize(double v) { return Double.toString(v); }
    static String __serialize(boolean v) { return v ? "true" : "false"; }
    static String __serialize(String v) {
        return "\"" + v.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }
    static String __serialize(int[] v) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < v.length; i++) {
            if (i > 0) sb.append(",");
            sb.append(__serialize(v[i]));
        }
        return sb.append("]").toString();
    }
    static String __serialize(double[] v) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < v.length; i++) {
            if (i > 0) sb.append(",");
            sb.append(__serialize(v[i]));
        }
        return sb.append("]").toString();
    }
    static String __serialize(String[] v) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < v.length; i++) {
            if (i > 0) sb.append(",");
            sb.append(__serialize(v[i]));
        }
        return sb.append("]").toString();
    }
'''

_CSHARP_CULTURE = "System.Globalization.CultureInfo.InvariantCulture"
_CSHARP_SERIALIZER = f'''
    static string __Serialize(int v) => v.ToString({_CSHARP_CULTURE});
    static string __Serialize(double v) => v.ToString({_CSHARP_CULTURE});
    static string __Serialize(bool v) => v ? "true" : "false";
    static string __Serialize(string v) =>
        "\\"" + v.Replace("\\\\", "\\\\\\\\").Replace("\\"", "\\\\\\"") + "\\"";
    static string __Serialize(int[] v) =>
        "[" + string.Join(",", System.Array.ConvertAll(v, __Serialize)) + "]";
    static string __Serialize(double[] v) =>
        "[" + string.Join(",", System.Array.ConvertAll(v, __Serialize)) + "]";
    static string __Serialize(string[] v) =>
        "[" + string.Join(",", System.Array.ConvertAll(v, __Serialize)) + "]";
'''


def _call_args(params: list[dict], args: list[Any], render) -> str:
    pairs = zip(params, args, strict=True)
    return ", ".join(render(param["type"], value) for param, value in pairs)


def build_python_source(question: CodingQuestion, code: str, args: list[Any]) -> str:
    signature = question.function_signature
    call_args = _call_args(signature["params"], args, render_literal_python)
    driver = (
        f"{_PYTHON_SERIALIZER}\n"
        f"__result = {question.class_name}().{signature['name']}({call_args})\n"
        "print(__serialize(__result))\n"
    )
    return f"{code}\n{driver}"


def build_java_source(question: CodingQuestion, code: str, args: list[Any]) -> str:
    """`code` must define `class {class_name}` *without* the `public`
    modifier (see starter_code) — Java requires the sole `public` class in a
    file to match the filename, so the generated driver below owns that spot
    as `public class Main`. It must also come *first* in the file: Piston
    runs Java via the single-file source-launcher (`java Main.java`), which
    — since the submitted filename doesn't match either class's name once
    Piston's own run script renames it — falls back to executing whichever
    top-level class appears first in the source, not the one named `Main`."""
    signature = question.function_signature
    call_args = _call_args(signature["params"], args, render_literal_java)
    return_type = JAVA_TYPE_MAP[signature["return_type"]]
    driver = f"""public class Main {{
{_JAVA_SERIALIZER}
    public static void main(String[] args) {{
        {return_type} __result = new {question.class_name}().{signature["name"]}({call_args});
        System.out.println(__serialize(__result));
    }}
}}
"""
    return f"{driver}\n{code}"


def build_csharp_source(question: CodingQuestion, code: str, args: list[Any]) -> str:
    """Same rationale as Java: `code` defines `class {class_name}`, and the
    driver appends its own `Program` class with `Main` — C# has no
    file/classname coupling, but keeping one entry point avoids ambiguity."""
    signature = question.function_signature
    call_args = _call_args(signature["params"], args, render_literal_csharp)
    return_type = CSHARP_TYPE_MAP[signature["return_type"]]
    driver = f"""

class Program {{
{_CSHARP_SERIALIZER}
    static void Main(string[] args) {{
        {return_type} __result = new {question.class_name}().{signature["name"]}({call_args});
        System.Console.WriteLine(__Serialize(__result));
    }}
}}
"""
    return f"{code}\n{driver}"


BUILDERS = {
    CodingLanguage.PYTHON: build_python_source,
    CodingLanguage.JAVA: build_java_source,
    CodingLanguage.CSHARP: build_csharp_source,
}

FILE_NAMES = {
    CodingLanguage.PYTHON: "main.py",
    CodingLanguage.JAVA: "Main.java",
    CodingLanguage.CSHARP: "Main.cs",
}


def build_source(
    language: CodingLanguage, question: CodingQuestion, code: str, args: list[Any]
) -> str:
    return BUILDERS[language](question, code, args)
