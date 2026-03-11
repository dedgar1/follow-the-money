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

## Prerequisites

- **Docker Desktop** (running)
- **Git**
- **uv** — Python package manager (`brew install uv` or `pip install uv`)
- **pnpm** — JS package manager (`npm install -g pnpm`)
- API keys (see [API keys](#api-keys) below — the FEC key has a free tier, Congress.gov is free)

---

## Running locally

```bash
git clone https://github.com/your-org/follow-the-money.git
cd follow-the-money
cp .env.example .env       # fill in API keys (see API keys section)
```

### Start the full stack

```bash
make dev
```

Builds all Docker images, starts every service, waits for health checks, seeds synthetic dev data, then prints:

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
make stop          # stops and removes containers; data volumes are preserved
```

### Reload after code changes

The API (uvicorn `--reload`) and frontend (Next.js HMR) pick up changes automatically. Only the Celery worker needs an explicit restart:

```bash
make reload        # restarts the Celery worker and beat scheduler only
```

### Rebuild after dependency changes

```bash
make rebuild       # rebuild Docker images (after pyproject.toml / package.json changes)
```

---

## Data: synthetic seed vs. real data

### Option A — Synthetic seed data (default, no API keys needed)

`make dev` automatically seeds the database with a realistic but entirely synthetic dataset (30 reps, 100 donors, contribution history, votes, alignment scores). This is the fastest way to explore the UI.

```bash
make seed          # add any new seed rows (idempotent, safe to re-run)
make seed-reset    # wipe all seed rows and re-insert from scratch
```

The seed script lives at `infrastructure/scripts/seed_dev_data.py`.

### Option B — Real data (requires API keys)

`load_real_data.py` runs the full ingest pipeline against live APIs — no Celery required. It calls each pipeline stage directly with configurable scope limits so you get a small but genuine dataset fast.

**Quickest real-data test — Senate only, 100 contributions per rep:**
```bash
uv run infrastructure/scripts/load_real_data.py --chamber senate --contributions 100
```

**Single state:**
```bash
uv run infrastructure/scripts/load_real_data.py --chamber senate --state CA
```

**Cap total reps (fast smoke test):**
```bash
uv run infrastructure/scripts/load_real_data.py --reps 10 --contributions 50 --skip-votes
```

**Finance data only (skip vote ingestion):**
```bash
uv run infrastructure/scripts/load_real_data.py --chamber senate --skip-votes
```

**All options:**

| Flag | Default | Description |
|---|---|---|
| `--chamber senate\|house\|both` | `both` | Which chamber(s) to load Congress members for |
| `--state XX` | all states | Filter to one state, e.g. `CA` |
| `--reps N` | unlimited | Cap total canonical reps processed |
| `--contributions N` | `200` | Max FEC contributions fetched per committee |
| `--cycle YYYY` | derived from config | FEC election cycle year, e.g. `2024` |
| `--congress N` | from config | Congress number, e.g. `119` |
| `--skip-fec` | off | Skip FEC contribution ingestion |
| `--skip-votes` | off | Skip vote ingestion and bill classification |

The script runs all 7 pipeline stages in order:

1. Seed canonical reps from Congress.gov
2. Fetch FEC contributions per rep's committee(s)
3. Ingest roll-call votes (House via Congress.gov, Senate via XML)
4. Classify bills with NLP keyword tagger
5. Resolve donor identities (rapidfuzz clustering)
6. Aggregate finance into relationships + Neo4j graph
7. Compute donor-vote alignment scores

---

## Running tests

```bash
make test                               # Python — uv run pytest (289 tests)
cd apps/web && pnpm test --run          # TypeScript — Vitest (5 tests)
```

---

## Data pipeline (production / Celery)

Runs nightly at 02:00 UTC. Each stage is a Celery task:

```
02:00  ingest_fec              — FEC Schedule A contributions → raw_filings
02:15  ingest_votes            — Congress.gov (House) + Senate.gov XML → raw_votes
04:00  resolve_identities      — rapidfuzz deduplication → canonical_reps / canonical_donors
04:30  classify_bills          — NLP keyword tagger → bills.industries
06:00  aggregate_finance       — DonorRepRelationships → PostgreSQL + Neo4j graph
07:00  compute_correlations    — AlignmentScore computation → alignment_scores
```

**Trigger individual stages manually** (stack must be running):

```bash
make task-ingest-fec
make task-ingest-votes
make task-resolve-identities
make task-classify-bills
make task-aggregate-finance
make task-compute-correlations
make pipeline                  # runs all stages in sequence
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
infrastructure/  Config, DB engine, Neo4j driver, Docker, seed scripts
```

The primary aggregate root is `DonorRepRelationship` — the financial relationship between one donor and one representative across all election cycles.

---

## API keys

| Key | Where to get it | Required? |
|---|---|---|
| `FEC_API_KEY` | [api.open.fec.gov](https://api.open.fec.gov/developers/) — free | No (falls back to `DEMO_KEY` at lower rate limits) |
| `CONGRESS_API_KEY` | [api.congress.gov/sign-up](https://api.congress.gov/sign-up/) — free | Yes for vote ingestion and real-data loading |
| `OPENSECRETS_API_KEY` | [opensecrets.org/api](https://www.opensecrets.org/api) — paid | No (optional industry enrichment) |

Add keys to your `.env` file:

```bash
FEC_API_KEY=your_key_here
CONGRESS_API_KEY=your_key_here
```

---

## Methodology

Alignment scores are only shown when all of the following are true:

- At least 5 relevant votes in the analysis window
- Shift magnitude ≥ 15 percentage points
- p-value < 0.05 (Fisher's exact test)
- Before/after window = 24 months on each side of the major donation event

See [docs/methodology.md](docs/methodology.md) for the full statistical methodology.

---

## Sprint progress

| Sprint | Focus | Status |
|---|---|---|
| 1 | Docker Compose · PostgreSQL schema · FastAPI skeleton · Next.js scaffold | Done |
| 2 | FEC adapter · Congress.gov + Senate XML adapters · Celery pipeline Stage 1 | Done |
| 3 | rapidfuzz entity resolver · canonical_reps/donors · identity resolution task | Done |
| 4 | Finance aggregation · Neo4j graph writes · DonorRepRelationship aggregates | Done |
| 5 | Homepage · Rep profile · Donor detail · REST API endpoints | Done |
| 6 | Neo4j multi-hop queries · D3 network graph | Done |
| 7 | Bill models · spaCy NLP classifier · voting record UI | Done |
| 8 | CorrelationEngine · AlignmentScore · timeline + heatmap viz | Done |
| 9 | Public REST API · CSV/JSON export · comparison view · platform stats · ticker | Done |
