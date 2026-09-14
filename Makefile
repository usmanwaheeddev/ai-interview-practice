.PHONY: up down migrate migration seed test test-backend test-frontend lint lint-backend lint-frontend interview-cli interview-sim ollama-pull piston-setup logs backup restore-rehearsal

up:
	@test -f .env || cp .env.example .env
	docker compose up -d --build
	@echo "API:      http://localhost:8005"
	@echo "API docs: http://localhost:8005/docs"
	@echo "Web: optional; docker compose --profile frontend up -d --build"
	@echo "MinIO:    http://localhost:9001 (minioadmin/minioadmin)"

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose exec api alembic upgrade head

migration:
	docker compose exec api alembic revision --autogenerate -m "$(m)"

seed:
	docker compose exec api python -m app.db.seed

test: test-backend

test-backend:
	docker compose exec api pytest

test-frontend:
	docker compose exec web npm run test

lint: lint-backend

lint-backend:
	docker compose exec api ruff check .
	docker compose exec api mypy app

lint-frontend:
	docker compose exec web npm run lint
	docker compose exec web npm run typecheck

interview-cli:
	docker compose exec api python -m app.cli.latency_spike --turns $(or $(turns),10)

interview-sim:
	docker compose exec api python -m app.cli.mock_smoke

ollama-pull:
	docker compose exec ollama ollama pull $(or $(model),llama3.2:1b)

# Installs Python/Java/C# support into the `piston` sandbox container — it
# ships with no languages preinstalled. Safe to rerun (skips already
# installed packages). Run after `make up` and before using the coding
# challenge feature.
piston-setup:
	docker compose exec api python -m app.cli.piston_setup

# Phase 6 hardening — see runbooks/restore-from-backup.md for the full
# procedure this automates and what to check when it's not a drill.
backup:
	@mkdir -p backups
	docker compose exec -T postgres pg_dump -U hiring -Fc hiring > backups/backup-$$(date +%Y%m%dT%H%M%S).dump
	@echo "Backup written to backups/ — never committed (see .gitignore)."

restore-rehearsal:
	@test -n "$(file)" || (echo "usage: make restore-rehearsal file=backups/backup-....dump" && exit 1)
	docker compose exec -T postgres psql -U hiring -d postgres -c "DROP DATABASE IF EXISTS restore_rehearsal;"
	docker compose exec -T postgres psql -U hiring -d postgres -c "CREATE DATABASE restore_rehearsal OWNER hiring;"
	docker compose exec -T postgres pg_restore -U hiring -d restore_rehearsal --no-owner --no-privileges < $(file)
	@echo "Restored into a throwaway 'restore_rehearsal' database — the real 'hiring' database was never touched."
	@echo "Spot-check it, then: docker compose exec postgres psql -U hiring -d postgres -c \"DROP DATABASE restore_rehearsal;\""
