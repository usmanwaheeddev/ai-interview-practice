# AI Interview Practice

A full-stack, self-hosted, AI-powered mock interview practice platform.
Users can upload resumes, practice interviews against a job description or a
spoken-language track, and receive transcript-based feedback. This is a personal
practice tool, not an automated hiring-decision system.

## Included in this release

- FastAPI API with JWT cookie authentication and user-owned resources.
- Resume extraction, interview planning, live voice interviews over WebSocket,
  and evidence-based scoring.
- Pluggable LLM, speech, and storage providers with test fakes.
- SQLAlchemy models, Alembic migrations, Redis-backed ARQ workers, and tests.
- User data export and account erasure endpoints.

The repository includes the backend and React frontend, including authentication,
interview setup, microphone preflight, live interviews, history, feedback reports,
and feedback reports. See [architecture.md](architecture.md) for runtime
components, data flows, domain models, and provider behavior.

## Stack

Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL 16, Redis 7, ARQ,
MinIO/S3, Ollama with optional Groq fallback, faster-whisper or whisper.cpp,
and Piper/espeak-ng. The frontend uses React 18, TypeScript, Vite,
Tailwind CSS, React Query, and React Router.

## Quick start

Install Docker and Docker Compose. Allow sufficient memory and disk for local
speech and language models; downloads can make the first startup slow.

```bash
git clone https://github.com/uwaheed88/ai-interview-practice.git
cd ai-interview-practice
cp .env.example .env
# Review .env and replace development credentials before deployment.
make up
make migrate
docker compose --profile frontend up -d --build
```

`make up` starts the API, worker, PostgreSQL, Redis, MinIO, Ollama (including a
model pull/warm-up job). The final command starts the included web
application using the opt-in `frontend` Compose profile.

- Web app: http://localhost:5173
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
Compose overrides database, Redis, object-storage, and Ollama addresses
with internal service names.

- `LLM_PROVIDER`: `ollama`, `groq`, or `fake`. Set `GROQ_API_KEY` only if needed.
- `STT_PROVIDER`: `faster_whisper` or `fake`; `STT_ENGINE` selects
  `faster_whisper` or `whisper_cpp`.
- `TTS_PROVIDER`: `piper` or `fake`.
- `STORAGE_PROVIDER`: `s3` or `fake`.

For Apple Silicon acceleration with whisper.cpp, run the API on the macOS host
and set `WHISPER_CPP_BINARY_PATH` and `WHISPER_CPP_MODEL_PATH` to your compiled
CLI and model. Docker Desktop's Linux VM cannot access Apple Metal.

Speech models and voice assets are local runtime downloads, not repository files.

## Development

```bash
make test          # Backend pytest suite; contract tests excluded by default.
make lint          # Backend Ruff and mypy checks.
make test-frontend # Frontend Vitest suite; start the frontend profile first.
make lint-frontend # Frontend ESLint and TypeScript checks.
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

For frontend development without Docker (Node.js 22.12+):

```bash
cd frontend
npm ci
VITE_API_URL=http://localhost:8005/api VITE_WS_URL=ws://localhost:8005 npm run dev
npm run build
npm run lint
npm run test
```

The frontend API and WebSocket addresses are configured at build/dev-server time
with `VITE_API_URL` and `VITE_WS_URL`; these variables must not contain secrets.

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
    providers/   LLM, speech, and storage adapters
    services/    Interview, scoring, and resume logic
    workers/     Background jobs
    ws/          Live interview transport
  alembic/       Database migrations
  tests/         Unit, API, and provider contract tests
  Dockerfile
frontend/
  src/
    components/  Layout, protected routes, and shared UI components
    features/    Authentication, interviews, and practice reports
    lib/         API client, auth context, and shared types
  Dockerfile     Development server image
architecture.md  System design and data flows
```

## Privacy and deployment safety

Resumes, transcripts, recordings, backups, and credentials must remain private.
Authenticated users can export their data at `GET /api/me/data-export` and erase
their account at `POST /api/me/erase`. Data persists until deleted; there is no
automatic retention schedule.

The example PostgreSQL, MinIO, and JWT credentials are development defaults.
Replace them, configure HTTPS and secure cookies, restrict exposed infrastructure
ports, and review access controls before deploying.

Historical Alembic revisions for the previously published coding feature remain
to preserve migration continuity. The active API, frontend, and Compose stack do
not include that feature or its execution sandbox.

`make backup` writes database snapshots to the ignored `backups/` directory.
`make restore-rehearsal file=backups/<snapshot>` restores into a separate rehearsal
database, not the application database.
