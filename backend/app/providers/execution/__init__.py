from functools import lru_cache

from app.core.config import get_settings
from app.providers.execution.base import ExecutionProvider
from app.providers.execution.fake import FakeExecutionProvider


@lru_cache
def get_execution_provider() -> ExecutionProvider:
    settings = get_settings()
    if settings.execution_provider == "fake":
        return FakeExecutionProvider()

    if settings.execution_provider == "piston":
        from app.providers.execution.piston import PistonExecutionProvider

        return PistonExecutionProvider(settings)

    raise NotImplementedError(
        f"Execution provider '{settings.execution_provider}' is not wired up. "
        "Use 'fake' or 'piston'."
    )
