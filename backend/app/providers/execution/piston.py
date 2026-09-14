import httpx

from app.core.config import Settings
from app.providers.execution.base import ExecutedFile, ExecutionResult
from app.providers.resilience import CircuitBreaker, call_with_resilience

# Piston (https://github.com/engineer-man/piston) API v2 — see
# app/services/coding/runtimes.py for the installed runtime names/versions.


class PistonExecutionProvider:
    def __init__(self, settings: Settings) -> None:
        self._client = httpx.AsyncClient(base_url=settings.piston_base_url, timeout=30.0)
        self._breaker = CircuitBreaker()

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
        async def _call() -> ExecutionResult:
            response = await self._client.post(
                "/api/v2/execute",
                json={
                    "language": language,
                    "version": version,
                    "files": [
                        {"name": f.name, "content": f.content} if f.name else {"content": f.content}
                        for f in files
                    ],
                    "compile_timeout": compile_timeout,
                    "run_timeout": run_timeout,
                    "compile_memory_limit": compile_memory_limit,
                    "run_memory_limit": run_memory_limit,
                },
            )
            response.raise_for_status()
            body = response.json()
            run = body["run"]
            compile_ = body.get("compile")
            return ExecutionResult(
                run_stdout=run["stdout"],
                run_stderr=run["stderr"],
                run_code=run.get("code"),
                run_signal=run.get("signal"),
                compile_stdout=compile_["stdout"] if compile_ else None,
                compile_stderr=compile_["stderr"] if compile_ else None,
                compile_code=compile_.get("code") if compile_ else None,
                compile_signal=compile_.get("signal") if compile_ else None,
            )

        # Timeout comfortably above Piston's own compile+run budget so the
        # wrapper never cuts off a submission Piston itself would still finish.
        return await call_with_resilience(
            _call,
            provider="piston",
            operation="execute",
            timeout_s=(compile_timeout + run_timeout) / 1000 + 10.0,
            max_retries=1,
            breaker=self._breaker,
        )

    async def health(self) -> bool:
        try:
            response = await self._client.get("/api/v2/runtimes", timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False
