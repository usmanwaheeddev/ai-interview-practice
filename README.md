# AI Interview Practice

AI Interview Practice is a self-hosted platform for realistic mock interviews. Candidates can practice by voice against a resume and job description or choose a subject and topic, review a live transcript, and receive evidence-grounded feedback. Camera recording is optional. This is a private practice tool, not an automated hiring-decision system.

The application has a React and TypeScript web client, a FastAPI backend, PostgreSQL for application data, Redis and ARQ for background work, and S3-compatible storage for resumes and interview recordings. It supports local Ollama models or the DeepSeek API for interview and scoring language tasks, plus local speech-to-text and text-to-speech providers.

## 1. Local setup with Ollama

Run PostgreSQL, Redis, and RustFS in Docker while running the API, worker, Ollama, and web app locally. Requirements: Python 3.12, Node.js 22.12+, Docker Compose, and [Ollama](https://ollama.com/download).

```bash
git clone https://github.com/uwaheed88/ai-interview-practice.git
cd ai-interview-practice
cp .env.example .env
ollama pull llama3.2:3b
```

In `.env`, configure local model use and service addresses:

```dotenv
LLM_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
DATABASE_URL=postgresql+asyncpg://hiring:hiring@localhost:5432/hiring
REDIS_URL=redis://localhost:6379/0
S3_ENDPOINT_URL=http://localhost:9000
S3_PUBLIC_ENDPOINT_URL=http://localhost:9000
```

Start the data services, install the backend, migrate the database, then run the API:

```bash
docker compose up -d postgres redis rustfs
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
set -a; source ../.env; set +a
alembic upgrade head
uvicorn app.main:app --reload --port 8005
```

In a second terminal, run the worker:

```bash
cd backend
source .venv/bin/activate
set -a; source ../.env; set +a
arq app.workers.settings.WorkerSettings
```

In a third terminal, run the frontend:

```bash
cd frontend
npm ci
VITE_PROXY_TARGET=http://127.0.0.1:8005 npm run dev
```

Open <http://localhost:5173>. Speech models download on first use. Set `STT_PROVIDER=fake` and `TTS_PROVIDER=fake` in `.env` only for development without local speech models.

## 2. Local setup with an API key

Use the same local services and application commands as part 1, with DeepSeek as the primary language model. Ollama provides an optional local fallback.

In `.env`, set:

```dotenv
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_MODEL=deepseek-flash
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
```

The backend calls DeepSeek first and falls back to Ollama if a request fails. Keep the key in `.env`, which is ignored by Git, and never put it in frontend variables. Start the data services, API, worker, and frontend using the commands in part 1.

## 3. Docker setup with Ollama

Docker Compose starts the web client, API, worker, PostgreSQL, Redis, RustFS, and Ollama. The default Compose setup pulls and warms the configured Ollama model. It defaults to DeepSeek with Ollama fallback; set `LLM_PROVIDER=ollama` to use only the local model.

```bash
git clone https://github.com/uwaheed88/ai-interview-practice.git
cd ai-interview-practice
cp .env.example .env
```

Set the model provider in `.env`:

```dotenv
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2:3b
```

Start the application and apply migrations:

```bash
make up
make migrate
```

The first run downloads the Ollama model and speech models, so startup and the first interview may take longer. Visit <http://localhost:5173>. API docs are at <http://localhost:8005/docs> and readiness at <http://localhost:8005/api/ready>. Allow enough memory and disk for the models.

## 4. Docker setup with an API key

Compose can use DeepSeek as its primary LLM and the included Ollama container as a fallback. This is the default configuration.

```bash
git clone https://github.com/uwaheed88/ai-interview-practice.git
cd ai-interview-practice
cp .env.example .env
```

Add your API key to `.env` and choose the DeepSeek provider:

```dotenv
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_MODEL=deepseek-flash
OLLAMA_MODEL=llama3.2:3b
```

Start the application and migrate:

```bash
make up
make migrate
```

DeepSeek handles language requests first; Ollama provides a local fallback when DeepSeek is unavailable. Keep `.env` private and do not place API keys in `VITE_*` settings. Open <http://localhost:5173> to use the application.

### Reprocess existing recordings

New and existing recordings are combined into one report player after upload. To create master files for recordings captured before this feature, run the reprocessor from the worker container after updating the application:

```bash
make reprocess-recordings
```

The command keeps the original chunks and prints any recordings that cannot be remuxed.

## Architecture and capabilities

See [architecture.md](architecture.md) for runtime components, data flows, domain models, and provider behavior.

- Resume extraction, interview planning, live voice interviews over WebSocket, transcript, and evidence-based scoring.
- Optional candidate video capture and private recording playback from the report.
- FastAPI with JWT cookie authentication and user-owned resources.
- DeepSeek and Ollama LLM integrations, faster-whisper or whisper.cpp speech recognition, and Piper speech synthesis.
- SQLAlchemy, Alembic migrations, Redis-backed ARQ workers, S3-compatible storage, account export, and erasure endpoints.

## Development commands

```bash
make test          # Backend pytest suite; contract tests excluded by default.
make lint          # Backend Ruff and mypy checks.
make test-frontend # Frontend Vitest suite.
make lint-frontend # Frontend ESLint and TypeScript checks.
make verify        # Complete pre-push quality gate.
make logs
make migration m="describe schema change"
make migrate
make down
```

To run backend tests without Docker:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e "[dev]"
pytest
```

For frontend development without Docker, follow the frontend commands in part 1. The Vite server proxies `/api` and `/ws` to `VITE_PROXY_TARGET`; frontend variables must not contain secrets.

Contract tests use real infrastructure and are opt-in with `pytest -m contract`. `make interview-sim` creates synthetic data and uses configured provider quota; run it only against a development environment.

## Production deployment

The production reference stack uses multi-stage images, an unprivileged API runtime, an Nginx-served frontend, same-origin REST/WebSocket proxying, health-gated startup, automatic Alembic migrations, persistent Redis state, and restart policies.

```bash
cp .env.production.example .env.production
# Replace every CHANGE_ME value and configure public HTTPS origins.
docker compose --env-file .env.production -f compose.production.yml config --quiet
docker compose --env-file .env.production -f compose.production.yml up -d --build
docker compose --env-file .env.production -f compose.production.yml ps
```

Terminate TLS in front of port 80 and expose the S3 API through the hostname in `S3_PUBLIC_ENDPOINT_URL`. The object-storage administration console binds only to `127.0.0.1:9001` in the production stack. Do not deploy with example credentials. Keep `.env.production` outside version control and back up PostgreSQL and object-storage volumes.

## Repository structure

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
frontend/
  src/
    components/  Layout, protected routes, and shared UI components
    features/    Authentication, interviews, and practice reports
    lib/         API client, auth context, and shared types
```
