# ADR 002 — Modular Monolith with Docker Compose

**Status**: Accepted
**Date**: 2026-03-09

## Context

The project needs multiple services (API, worker, frontend, 3 databases) but
is early-stage with a small team.

## Decision

Deploy as a modular monolith behind Docker Compose locally, targeting Railway
(backend) + Vercel (frontend) in production. Bounded contexts are enforced by
Python module boundaries and interface contracts, not separate deployments.

## Consequences

- `docker-compose up` starts everything with one command
- Bounded contexts can be extracted to microservices later if needed
- No service mesh or inter-service HTTP in Sprint 1
- Celery workers are the only "separate service" pattern
