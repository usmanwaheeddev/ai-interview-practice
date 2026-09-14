from app.providers.execution.base import ExecutedFile, ExecutionResult


class FakeExecutionProvider:
    """Never actually runs submitted code — returns a fixed, empty-output
    result regardless of input, deterministic for tests. See
    FakeSTTProvider/FakeLLMProvider for the same pattern. Comparisons against
    a real `expected_output` will honestly come back "failed"; this fake
    exists to exercise the submit/persist/response plumbing, not grading
    correctness — see tests/test_coding_harness.py and
    tests/test_coding_canonical.py for that."""

    async def execute(
        self,
        *,
        language: str,
        version: str,
        files: list[ExecutedFile],
        compile_timeout: int,
        run_timeout: int,
        compile_memory_limit: int,
        run_memory_limit: int,
    ) -> ExecutionResult:
        return ExecutionResult(run_stdout="", run_stderr="", run_code=0, run_signal=None)

    async def health(self) -> bool:
        return True
