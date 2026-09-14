from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.db.models import User
from app.providers.llm.base import LLMProvider
from app.providers.llm.groq import GroqLLMProvider

router = APIRouter(prefix="/provider-tests", tags=["provider tests"])


class GroqTestRequest(BaseModel):
    prompt: str = Field(
        default="Reply with exactly: Groq connection successful",
        min_length=1,
        max_length=500,
    )


class GroqTestResponse(BaseModel):
    status: str
    provider: str
    model: str
    response: str


def get_groq_test_provider(settings: Annotated[Settings, Depends(get_settings)]) -> LLMProvider:
    if settings.env != "development" or not settings.debug:
        raise NotFoundError("Provider test endpoints are only available in development")
    if not settings.groq_api_key:
        raise ServiceUnavailableError(
            "GROQ_API_KEY is not configured",
            code="groq_not_configured",
        )
    return GroqLLMProvider(settings)


@router.post(
    "/groq",
    response_model=GroqTestResponse,
    summary="Test the Groq API connection",
    description=(
        "Sends a small completion request to the configured Groq model. "
        "This development-only endpoint requires an authenticated session "
        "and consumes provider quota."
    ),
)
async def test_groq_connection(
    body: GroqTestRequest,
    _: Annotated[User, Depends(get_current_user)],
    provider: Annotated[LLMProvider, Depends(get_groq_test_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GroqTestResponse:
    try:
        response = await provider.complete(
            system="You are a concise API connectivity test.",
            user=body.prompt,
            max_tokens=40,
        )
    except Exception as exc:
        raise ServiceUnavailableError(
            "Groq API request failed; check the API key, model, and backend logs",
            code="groq_test_failed",
        ) from exc

    return GroqTestResponse(
        status="ok",
        provider="groq",
        model=settings.groq_model,
        response=response,
    )
