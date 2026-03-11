COMPOSE = docker compose -f infrastructure/docker/docker-compose.yml

.PHONY: dev stop reload rebuild up up-d down build logs seed seed-reset test lint codegen

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
