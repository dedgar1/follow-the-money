COMPOSE = docker compose -f infrastructure/docker/docker-compose.yml

.PHONY: dev stop reload rebuild up up-d down build logs seed seed-reset test lint codegen \
        pipeline task-ingest-fec task-ingest-votes task-resolve-identities \
        task-classify-bills task-aggregate-finance task-compute-correlations

# ── Primary commands ──────────────────────────────────────────────────────────

## Start the full stack, wait for health, seed dev data, print URLs.
dev:
	@echo "Building images…"
	@$(COMPOSE) build --quiet
	@echo "Starting services…"
	@$(COMPOSE) up -d
	@echo "Waiting for Postgres…"
	@until $(COMPOSE) exec -T postgres pg_isready -U ftm -q; do sleep 1; done
	@echo "Waiting for API…"
	@until curl -sf http://localhost:8000/health > /dev/null; do sleep 2; done
	@echo "Seeding dev data…"
	@$(COMPOSE) exec -T api python infrastructure/scripts/seed_dev_data.py
	@echo ""
	@echo "  ✓  Follow the Money is running"
	@echo ""
	@echo "  Frontend  →  http://localhost:3000"
	@echo "  API docs  →  http://localhost:8000/docs"
	@echo "  GraphQL   →  http://localhost:8000/graphql"
	@echo "  Neo4j     →  http://localhost:7474"
	@echo "  Flower    →  http://localhost:5555"
	@echo ""
	@echo "  Run 'make stop' to shut down."

## Reload code changes into the running dev stack.
##
## The API (uvicorn --reload) and frontend (Next.js HMR) pick up changes
## automatically — only the Celery worker needs an explicit restart.
## Use this after editing pipeline tasks or any other worker code.
reload:
	@echo "Restarting Celery worker and beat…"
	@$(COMPOSE) restart worker beat
	@echo "Done. API and frontend are already live-reloading."

## Rebuild Docker images then restart all services.
##
## Use this after adding/removing Python packages (pyproject.toml) or
## npm packages (package.json).  Leaves data volumes intact.
rebuild:
	@echo "Rebuilding images…"
	@$(COMPOSE) build
	@echo "Restarting services…"
	@$(COMPOSE) up -d
	@echo "Done."

## Stop and remove all containers (data volumes are preserved).
stop:
	@echo "Stopping Follow the Money…"
	@$(COMPOSE) down
	@echo "Done."

# ── Lower-level helpers ───────────────────────────────────────────────────────

up:
	$(COMPOSE) up

up-d:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build

logs:
	$(COMPOSE) logs -f

seed:
	$(COMPOSE) exec -T api python infrastructure/scripts/seed_dev_data.py

seed-reset:
	$(COMPOSE) exec -T api python infrastructure/scripts/seed_dev_data.py --reset

# ── Dev tools ─────────────────────────────────────────────────────────────────

test:
	uv run pytest

lint:
	uv run ruff check .

codegen:
	pnpm --filter web codegen

# ── Pipeline — manual task execution ──────────────────────────────────────────
#
# Each target sends the task to the running Celery worker via the broker.
# Requires: make up (stack must be running).
#
# Run the full pipeline in order:
#   make pipeline
#
# Run individual stages:
#   make task-ingest-fec
#   make task-ingest-votes
#   make task-resolve-identities
#   make task-classify-bills
#   make task-aggregate-finance
#   make task-compute-correlations

CELERY_CALL = $(COMPOSE) exec -T api celery --app=pipeline.celery_app.celery_app call

## Run all pipeline stages in sequence (blocking).
pipeline: task-ingest-fec task-ingest-votes task-resolve-identities task-classify-bills task-aggregate-finance task-compute-correlations
	@echo "Pipeline complete."

## Stage 1 — Fetch FEC contribution filings into raw tables.
task-ingest-fec:
	@echo "Running ingest_fec…"
	@$(CELERY_CALL) pipeline.tasks.ingest_fec.run
	@echo "ingest_fec done."

## Stage 2 — Fetch roll call votes from Congress.gov + Senate XML.
task-ingest-votes:
	@echo "Running ingest_votes…"
	@$(CELERY_CALL) pipeline.tasks.ingest_votes.run
	@echo "ingest_votes done."

## Stage 3 — Resolve raw donors/reps into canonical entities.
task-resolve-identities:
	@echo "Running resolve_identities…"
	@$(CELERY_CALL) pipeline.tasks.resolve_identities.run
	@echo "resolve_identities done."

## Stage 4 — NLP-classify bills into industry categories.
task-classify-bills:
	@echo "Running classify_bills…"
	@$(CELERY_CALL) pipeline.tasks.classify_bills.run
	@echo "classify_bills done."

## Stage 5 — Aggregate finance data into rollups + Neo4j graph.
task-aggregate-finance:
	@echo "Running aggregate_finance…"
	@$(CELERY_CALL) pipeline.tasks.aggregate_finance.run
	@echo "aggregate_finance done."

## Stage 6 — Compute donor-vote alignment scores (CorrelationEngine).
task-compute-correlations:
	@echo "Running compute_correlations…"
	@$(CELERY_CALL) pipeline.tasks.compute_correlations.run
	@echo "compute_correlations done."
