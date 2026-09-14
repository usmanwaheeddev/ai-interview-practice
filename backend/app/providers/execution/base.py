from dataclasses import dataclass
from typing import Protocol


@dataclass
class ExecutedFile:
    content: str
    name: str | None = None


@dataclass
class ExecutionResult:
    """Mirrors Piston's /api/v2/execute response shape (see docs referenced
    in app/providers/execution/piston.py) so callers stay decoupled from the
    real provider's wire format."""

    run_stdout: str
    run_stderr: str
    run_code: int | None
    run_signal: str | None
    compile_stdout: str | None = None
    compile_stderr: str | None = None
    compile_code: int | None = None
    compile_signal: str | None = None


class ExecutionProvider(Protocol):
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
    ) -> ExecutionResult: ...

    async def health(self) -> bool: ...
