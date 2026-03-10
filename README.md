# Follow the Money

A civic transparency platform that makes campaign finance data visible, searchable, and understandable. Find your elected representatives, see who funds them, and — uniquely — see whether their voting behavior shifted after receiving significant donations from a donor industry.

Every correlation shown is factual, statistically defensible, and links to its source data. Correlation ≠ causation is always stated explicitly.

---

## What it does

- **Find your rep** — search by name, ZIP code, state, or browse the map
- **See the money** — who donated, how much, from which industries, across which election cycles
- **Follow the votes** — roll call voting record with industry tags on every bill
- **Spot the shift** — before/after alignment scores showing whether voting patterns changed after major donations (minimum 5 votes, 15-point shift, p < 0.05)

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (TypeScript) + Tailwind + D3 |
| Internal API | GraphQL via Strawberry (Python) |
| Public API | REST via FastAPI |
| Primary DB | PostgreSQL 16 |
| Graph DB | Neo4j 5 (donor network traversal) |
| Job queue | Celery + Redis |
| Entity resolution | rapidfuzz (deduplicates donor names) |
| Data sources | FEC API · Congress.gov API v3 · Senate.gov XML feeds |

---

## Running locally

**Prerequisites:** Docker Desktop (running), Git

```bash
git clone https://github.com/your-org/follow-the-money.git
cd follow-the-money
cp .env.example .env        # add API keys if you have them (see below)
```

### Start

```bash
make dev
```

Builds images, starts all services, waits for health checks, seeds sample data, then prints:

```
  ✓  Follow the Money is running

  Frontend  →  http://localhost:3000
  API docs  →  http://localhost:8000/docs
  GraphQL   →  http://localhost:8000/graphql
  Neo4j     →  http://localhost:7474
  Flower    →  http://localhost:5555
```

### Stop

```bash
make stop
```

### Re-seed data

```bash
make seed          # add any new seed rows (idempotent)
make seed-reset    # wipe seed rows and re-insert from scratch
```

### Tests

```bash
make test                              # Python — pytest (237 tests)
cd apps/web && pnpm test --run         # TypeScript — Vitest (5 tests)
```

---

## Data pipeline

Runs nightly at 02:00 UTC. Each stage is a Celery task:

```
02:00  ingest_fec         — FEC Schedule A contributions → raw_filings
02:15  ingest_votes       — Congress.gov (House) + Senate.gov XML → raw_votes
04:00  resolve_identities — rapidfuzz deduplication → canonical_reps / canonical_donors
06:00  aggregate_finance  — build DonorRepRelationships → PostgreSQL + Neo4j graph
```

Trigger any stage manually:
```bash
docker exec -it $(docker ps -qf name=worker) \
  celery -A pipeline.celery_app call pipeline.tasks.ingest_fec.run
```

**Failure mode: FAIL LOUD.** Any stage failure sends an alert and halts downstream stages. The last successful dataset continues to be served with a staleness banner.

---

## Architecture

Hexagonal (Ports & Adapters). The domain core is pure Python — no SQLAlchemy, no FastAPI, no Redis imports anywhere in `domain/`.

```
domain/          Pure Python models and service logic
adapters/        Postgres, Neo4j, FEC API, Congress.gov, rapidfuzz
apps/api/        FastAPI + Strawberry GraphQL
apps/web/        Next.js frontend
pipeline/        Celery tasks (one per pipeline stage)
infrastructure/  Config, DB engine, Neo4j driver, Docker
```

The primary aggregate root is `DonorRepRelationship` — the financial relationship between one donor and one representative across all election cycles.

---

## API keys

| Key | Where to get it | Required? |
|---|---|---|
| `FEC_API_KEY` | [api.open.fec.gov](https://api.open.fec.gov/developers/) — free | No (falls back to `DEMO_KEY` with rate limits) |
| `CONGRESS_API_KEY` | [api.congress.gov/sign-up](https://api.congress.gov/sign-up/) — free | Yes for vote ingestion |
| `OPENSECRETS_API_KEY` | [opensecrets.org/api](https://www.opensecrets.org/api) — paid | No (used for industry tags in Sprint 7+) |

---

## Sprint progress

| Sprint | Focus | Status |
|---|---|---|
| 1 | Docker Compose · PostgreSQL schema · FastAPI skeleton · Next.js scaffold | Done |
| 2 | FEC adapter · Congress.gov + Senate XML adapters · Celery pipeline Stage 1 | Done |
| 3 | rapidfuzz entity resolver · canonical_reps/donors · identity resolution task | Done |
| 4 | Finance aggregation · Neo4j graph writes · DonorRepRelationship aggregates | Done |
| 5 | Homepage · Rep profile · Donor detail · REST API endpoints | Done |
| 6 | Neo4j multi-hop queries · D3 network graph | Planned |
| 7 | Bill models · spaCy NLP classifier · voting record UI | Planned |
| 8 | CorrelationEngine · AlignmentScore · timeline + heatmap viz | Planned |
| 9 | Public REST API · CSV export · embeddable widget · comparison view | Planned |

---

## Methodology

Alignment scores are only shown when all of the following are true:

- At least 5 relevant votes in the analysis window
- Shift magnitude ≥ 15 percentage points
- p-value < 0.05 (Fisher's exact test)
- Before/after window = 24 months on each side of the major donation event

See [docs/methodology.md](docs/methodology.md) for the full statistical methodology.
