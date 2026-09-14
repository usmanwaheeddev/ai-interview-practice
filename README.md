# AI Hiring Interview

Backend for a self-hosted, AI-powered mock interview and coding-practice platform.
Users can upload resumes, practice interviews against a job description or a
spoken-language track, and receive transcript-based feedback. This is a personal
practice tool, not an automated hiring-decision system.

## Included in this release

- FastAPI API with JWT cookie authentication and user-owned resources.
- Resume extraction, interview planning, live voice interviews over WebSocket,
  and evidence-based scoring.
- Coding challenges with sandboxed execution, AI reviews, and hints.
- Pluggable LLM, speech, storage, and execution providers with test fakes.
- SQLAlchemy models, Alembic migrations, Redis-backed ARQ workers, and tests.
- User data export and account erasure endpoints.

The frontend directory is a placeholder in this repository. Frontend application
source is not included in this backend release.

## Stack

Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL 16, Redis 7, ARQ,
MinIO/S3, Ollama with optional Groq fallback, faster-whisper or whisper.cpp,
Piper/espeak-ng, and Piston.

## Quick start

Install Docker and Docker Compose. Allow sufficient memory and disk for local
speech and language models; downloads can make the first startup slow.

```bash
git clone https://github.com/uwaheed88/ai-hiring-interview.git
cd ai-hiring-interview
cp .env.example .env
# Review .env and replace development credentials before deployment.
make up
make migrate
make piston-setup  # Install sandbox runtimes if using coding challenges.
```

`make up` starts the API, worker, PostgreSQL, Redis, MinIO, Ollama (including a
model pull/warm-up job), and Piston. The frontend service is opt-in via the
`frontend` Compose profile and requires frontend source to be available locally.

- API: http://localhost:8005
- Swagger: http://localhost:8005/docs
- ReDoc: http://localhost:8005/redoc
- Liveness: http://localhost:8005/health
- Readiness: http://localhost:8005/ready
- MinIO console: http://localhost:9001

Readiness checks access infrastructure and configured providers, and may download
or load models on the first call. Optional `make seed` creates local practice data.

## Configuration

Use `.env.example` as the configuration reference. Never commit the real `.env`.
Compose overrides database, Redis, object-storage, Ollama, and Piston addresses
with internal service names.

- `LLM_PROVIDER`: `ollama`, `groq`, or `fake`. Set `GROQ_API_KEY` only if needed.
- `STT_PROVIDER`: `faster_whisper` or `fake`; `STT_ENGINE` selects
  `faster_whisper` or `whisper_cpp`.
- `TTS_PROVIDER`: `piper` or `fake`.
- `STORAGE_PROVIDER`: `s3` or `fake`.
- `EXECUTION_PROVIDER`: `piston` or `fake`.

For Apple Silicon acceleration with whisper.cpp, run the API on the macOS host
and set `WHISPER_CPP_BINARY_PATH` and `WHISPER_CPP_MODEL_PATH` to your compiled
CLI and model. Docker Desktop's Linux VM cannot access Apple Metal.

Speech models and voice assets are local runtime downloads, not repository files.

## Development

```bash
make test          # Backend pytest suite; contract tests excluded by default.
make lint          # Backend Ruff and mypy checks.
make logs
make migration m="describe schema change"
make migrate
make down
```

To run tests without Docker:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Contract tests use real infrastructure and are opt-in (`pytest -m contract`).
`make interview-sim` creates synthetic data and uses configured provider quota;
run it only against a development environment.

The Compose API and worker bind-mount the backend for development. Restart the
worker after changing worker code. The Dockerfile includes development tools;
this Compose configuration is not a hardened production deployment.

## Structure

```text
backend/
  app/
    api/         HTTP routes and schemas
    core/        Configuration, authentication, logging, and dependencies
    db/          Models, sessions, and seed data
    providers/   LLM, speech, storage, and execution adapters
    services/    Interview, scoring, resume, and coding logic
    workers/     Background jobs
    ws/          Live interview transport
  alembic/       Database migrations
  tests/         Unit, API, and provider contract tests
  Dockerfile
frontend/        Placeholder for a future frontend release
```

## Privacy and deployment safety

Resumes, transcripts, recordings, backups, and credentials must remain private.
Authenticated users can export their data at `GET /api/me/data-export` and erase
their account at `POST /api/me/erase`. Data persists until deleted; there is no
automatic retention schedule.

The example PostgreSQL, MinIO, and JWT credentials are development defaults.
Replace them, configure HTTPS and secure cookies, restrict exposed infrastructure
ports, and review access controls before deploying. Piston runs privileged in
this development stack; isolate it from sensitive workloads.

`make backup` writes database snapshots to the ignored `backups/` directory.
`make restore-rehearsal file=backups/<snapshot>` restores into a separate rehearsal
database, not the application database.
