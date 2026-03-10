COMPOSE = docker compose -f infrastructure/docker/docker-compose.yml

.PHONY: up down build logs test lint codegen

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

test:
	uv run pytest

lint:
	uv run ruff check .

codegen:
	pnpm --filter web codegen
