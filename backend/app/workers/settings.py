from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.workers.interview_jobs import generate_mock_plan
from app.workers.resume_jobs import parse_resume
from app.workers.scoring_jobs import score_mock_interview

settings = get_settings()
configure_logging(settings.debug)


async def ping(ctx: dict) -> str:
    return "pong"


class WorkerSettings:
    functions = [ping, parse_resume, generate_mock_plan, score_mock_interview]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    job_timeout = 300
