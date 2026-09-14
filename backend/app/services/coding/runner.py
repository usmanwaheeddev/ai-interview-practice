"""Orchestrates a full submission run: one Piston /execute call per test
case (simplest, and gives per-test-case runtime/stderr independently — see
phases.md's coding-challenge spec §4.4), parses+compares canonical output,
and classifies compile errors, runtime exceptions/timeouts, and normal
test-assertion failures separately."""

import time
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.db.models.coding import CodingLanguage, CodingQuestion, CodingTestCase
from app.providers.execution.base import ExecutedFile, ExecutionProvider
from app.services.coding.canonical import CanonicalParseError, outputs_match, parse_canonical
from app.services.coding.harness import FILE_NAMES, build_source
from app.services.coding.runtimes import PISTON_LANGUAGE_NAME, RUNTIME_VERSIONS

# Sandbox stderr can contain container paths/hostnames — never forward it to
# the client untrimmed. Full text is still persisted in CodingSubmission.results
# for internal debugging; the API layer decides what a hidden case may show.
_STDERR_MAX_CHARS = 4000


@dataclass
class TestCaseResult:
    test_case_id: str
    passed: bool
    actual_output: Any
    expected_output: Any
    stderr: str
    runtime_ms: int


@dataclass
class SubmissionOutcome:
    status: str  # "passed" | "failed" | "error"
    results: list[TestCaseResult]
    error_message: str | None


def _sanitize(text: str | None) -> str:
    return (text or "")[:_STDERR_MAX_CHARS]


async def run_submission(
    *,
    execution_provider: ExecutionProvider,
    settings: Settings,
    question: CodingQuestion,
    test_cases: list[CodingTestCase],
    language: CodingLanguage,
    code: str,
) -> SubmissionOutcome:
    return_type = question.function_signature["return_type"]
    results: list[TestCaseResult] = []

    for test_case in test_cases:
        source = build_source(language, question, code, test_case.args)
        started = time.monotonic()
        exec_result = await execution_provider.execute(
            language=PISTON_LANGUAGE_NAME[language.value],
            version=RUNTIME_VERSIONS[language.value],
            files=[ExecutedFile(content=source, name=FILE_NAMES[language])],
            compile_timeout=settings.piston_compile_timeout_ms,
            run_timeout=settings.piston_run_timeout_ms,
            compile_memory_limit=settings.piston_compile_memory_limit_bytes,
            run_memory_limit=settings.piston_run_memory_limit_bytes,
        )
        runtime_ms = round((time.monotonic() - started) * 1000)

        if exec_result.compile_code not in (None, 0):
            # Same user code compiles identically for every test case — no
            # point burning sandbox time re-failing it for each one. Only
            # C# has a real separate compile stage in this Piston setup;
            # Java runs via `java Foo.java` (the single-file source
            # launcher), so a Java syntax error surfaces as a normal
            # per-test-case run failure below instead — still correctly
            # marked not-passed with the compiler diagnostic in stderr, just
            # without this short-circuit.
            return SubmissionOutcome(
                status="error",
                results=[
                    TestCaseResult(
                        test_case_id=str(test_case.id),
                        passed=False,
                        actual_output=None,
                        expected_output=test_case.expected_output,
                        stderr=_sanitize(exec_result.compile_stderr),
                        runtime_ms=runtime_ms,
                    )
                ],
                error_message="Compile error",
            )

        if exec_result.run_signal is not None or exec_result.run_code not in (None, 0):
            # Either a timeout (Piston kills the process — signal set) or an
            # uncaught runtime exception (nonzero exit, no signal).
            results.append(
                TestCaseResult(
                    test_case_id=str(test_case.id),
                    passed=False,
                    actual_output=None,
                    expected_output=test_case.expected_output,
                    stderr=_sanitize(exec_result.run_stderr),
                    runtime_ms=runtime_ms,
                )
            )
            continue

        try:
            actual = parse_canonical(exec_result.run_stdout.strip())
            passed = outputs_match(actual, test_case.expected_output, return_type)
        except CanonicalParseError:
            actual = None
            passed = False

        results.append(
            TestCaseResult(
                test_case_id=str(test_case.id),
                passed=passed,
                actual_output=actual,
                expected_output=test_case.expected_output,
                stderr=_sanitize(exec_result.run_stderr),
                runtime_ms=runtime_ms,
            )
        )

    status = "passed" if all(r.passed for r in results) else "failed"
    return SubmissionOutcome(status=status, results=results, error_message=None)
