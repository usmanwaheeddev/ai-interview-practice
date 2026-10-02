# AI Interview Practice

A production-oriented, self-hosted AI mock-interview platform with real-time
voice conversations, resilient AI-provider integrations, evidence-grounded
feedback, and privacy controls.
Users can upload resumes, practice interviews against a job description or a
programming-language track, and receive transcript-based feedback. This is a
personal practice tool, not an automated hiring-decision system.

## Included in this release

- FastAPI API with JWT cookie authentication and user-owned resources.
- Resume extraction, interview planning, live voice interviews over WebSocket,
  and evidence-based scoring.
- DeepSeek-first LLM calls with local Ollama fallback, plus local speech
  providers and deterministic test fakes.
- SQLAlchemy models, Alembic migrations, Redis-backed ARQ workers, and tests.
- User data export and account erasure endpoints.

The repository includes the backend and React frontend, including authentication,
interview setup, microphone preflight, live interviews, history, feedback reports,
and privacy controls. See [architecture.md](architecture.md) for runtime
components, data flows, domain models, and provider behavior.

## Stack

Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL 16, Redis 7, ARQ,
RustFS/S3, DeepSeek with local Ollama fallback, faster-whisper or whisper.cpp,
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
```

`make up` starts the API, worker, PostgreSQL, Redis, RustFS, Ollama (including a
model pull/warm-up job), and the web application. `make up-backend` starts the
same backend stack without the frontend profile.

- Web app: http://localhost:5173
- API: http://localhost:8005
- Swagger: http://localhost:8005/docs
- ReDoc: http://localhost:8005/redoc
- Liveness: http://localhost:8005/api/health
- Readiness: http://localhost:8005/api/ready
- Object-storage console: http://localhost:9001

Readiness checks access infrastructure and configured providers, and may download
or load models on the first call. Optional `make seed` creates local practice data.

## Configuration

Use `.env.example` as the configuration reference. Never commit the real `.env`.
Compose overrides database, Redis, object-storage, and Ollama addresses
with internal service names.

- `LLM_PROVIDER`: `deepseek`, `ollama`, or `fake`. DeepSeek is primary and
  automatically falls back to local Ollama when a request fails.
- `STT_PROVIDER`: `faster_whisper` or `fake`; `STT_ENGINE` selects
  `faster_whisper` or `whisper_cpp`.
- `TTS_PROVIDER`: `piper` or `fake`.
- `STORAGE_PROVIDER`: `s3` or `fake`.

For Apple Silicon acceleration with whisper.cpp, run the API on the macOS host
and set `WHISPER_CPP_BINARY_PATH` and `WHISPER_CPP_MODEL_PATH` to your compiled
CLI and model. Docker Desktop's Linux VM cannot access Apple Metal.

For Apple Silicon Ollama acceleration, run Ollama natively on macOS and set
`OLLAMA_DOCKER_URL=http://host.docker.internal:11434`. The default Compose path
uses the free CPU-only Ollama container.

DeepSeek uses its official OpenAI-compatible API. Set `LLM_PROVIDER=deepseek`
and `DEEPSEEK_API_KEY`; `DEEPSEEK_MODEL` defaults to `deepseek-flash`, with
thinking disabled for lower live-interview latency. Failed DeepSeek requests
fall back to the local model configured by `OLLAMA_URL` and `OLLAMA_MODEL`.

Piper voices are downloaded lazily on first use. In Docker they persist in the
`piper_voices` volume. Live interviews currently use English speech. When the
API runs directly with Uvicorn,
`PIPER_VOICES_DIR` is optional: the app chooses a writable per-user cache
(`~/Library/Caches/ai-interview-practice/piper-voices` on macOS,
`~/.cache/ai-interview-practice/piper-voices` on Linux, or the local app-data
directory on Windows). Override it only when a specific location is required.
Whisper models are also runtime downloads rather than repository files.

## Interview flow

Creating an interview in the UI first stores only a draft in browser session
storage. No database interview or provider job is created until the candidate
reaches device setup, grants microphone access, accepts the recording/feedback
consent, and selects **Begin interview**. The generated interview ID is retained
across a preflight reload so retrying does not create a duplicate session.

Resume interviews generate the full question bank in one structured LLM request:
five questions for 15 minutes or ten for 30 minutes, distributed across the
selected areas. The live engine can ask follow-ups and continues through the
bank until the configured time threshold, so a single selected area does not
end the interview after only one question. The opening greeting uses the logged-in
candidate's full name.

## Engineering highlights

- Deterministic interview state machine with Redis-backed reconnect recovery.
- Streaming voice transport with bounded VAD, overlapping STT segments, partial
  transcripts, bounded Director prompts, and sentence-sized audio chunks.
- Provider isolation with timeouts, retries, circuit breakers, and LLM fallback.
- Evidence validation prevents feedback from citing transcript text that was
  never spoken.
- Resource ownership is enforced at every API boundary; personal-data export
  and complete erasure are first-class endpoints.
- Background jobs are retryable and preserve user data when providers fail.
- Separate development and production container builds, automated migrations,
  health checks, non-root runtime, and same-origin WebSocket proxying.

## Development

```bash
make test          # Backend pytest suite; contract tests excluded by default.
make lint          # Backend Ruff and mypy checks.
make test-frontend # Frontend Vitest suite; start the frontend profile first.
make lint-frontend # Frontend ESLint and TypeScript checks.
make verify        # Complete pre-push quality gate.
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

To run the API and worker directly while keeping the data services in Docker:

```bash
make up-backend
docker compose stop api worker
cd backend
source .venv/bin/activate
set -a; source ../.env; set +a
alembic upgrade head
uvicorn app.main:app --reload --port 8005
# In a second activated terminal, load ../.env the same way:
arq app.workers.settings.WorkerSettings
```

For this host-run mode, keep `DATABASE_URL`, `REDIS_URL`, `S3_ENDPOINT_URL`, and
`OLLAMA_URL` pointed at their localhost ports. Piper works without an explicit
voices directory and downloads its voice on the first readiness or synthesis
request.

Contract tests use real infrastructure and are opt-in (`pytest -m contract`).
`make interview-sim` creates synthetic data and uses configured provider quota;
run it only against a development environment.
For a minimal DeepSeek connectivity check, activate the backend environment and
run `python model_test.py`; it reads `DEEPSEEK_API_KEY` from the repository-root
`.env` file or the process environment.

For frontend development without Docker (Node.js 22.12+):

```bash
cd frontend
npm ci
VITE_PROXY_TARGET=http://127.0.0.1:8005 npm run dev
npm run build
npm run lint
npm run test
```

The Vite dev server proxies same-origin `/api` and `/ws` traffic to
`VITE_PROXY_TARGET`. `VITE_API_URL` and `VITE_WS_URL` remain available when a
deployment intentionally bypasses that proxy; none of these variables may
contain secrets.

The Compose API and worker bind-mount the backend for development. Restart the
worker after changing worker code. The Dockerfile includes development tools;
this Compose configuration is not a hardened production deployment.

## Production container deployment

The production reference stack uses multi-stage images, an unprivileged API
runtime, an Nginx-served frontend, same-origin REST/WebSocket proxying,
health-gated startup, automatic Alembic migrations, persistent Redis state, and
restart policies.

```bash
cp .env.production.example .env.production
# Replace every CHANGE_ME value and configure public HTTPS origins.
docker compose --env-file .env.production -f compose.production.yml config --quiet
docker compose --env-file .env.production -f compose.production.yml up -d --build
docker compose --env-file .env.production -f compose.production.yml ps
```

Terminate TLS in front of port 80 and expose the S3 API through the hostname in
`S3_PUBLIC_ENDPOINT_URL`. The object-storage administration console binds only
to `127.0.0.1:9001` in the production stack. The production Compose file also
runs and preloads the local Ollama fallback. On a small CPU-only VM it may be
slow; keep Whisper `base` as shown in the example configuration and size the VM
for both speech and language models.

Do not deploy with example credentials. Keep `.env.production` outside version
control and back up the PostgreSQL and object-storage volumes.

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

The example PostgreSQL, object-storage, and JWT credentials are development defaults.
Replace them, configure HTTPS and secure cookies, restrict exposed infrastructure
ports, and review access controls before deploying.

Historical Alembic revisions for the previously published coding feature remain
to preserve migration continuity. The active API, frontend, and Compose stack do
not include that feature or its execution sandbox.

`make backup` writes database snapshots to the ignored `backups/` directory.
`make restore-rehearsal file=backups/<snapshot>` restores into a separate rehearsal
database, not the application database.
