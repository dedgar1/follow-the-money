# CLAUDE.md — Follow the Money
> Read this file at the start of every session. It contains the full architectural context for this project.

---

## What This Project Is

**Follow the Money** is a civic transparency platform that makes campaign finance data visible, searchable, and understandable. Users can find their elected representatives, see who funds them, and — uniquely — see whether a representative's voting behavior shifted after receiving significant donations from a donor industry.

The platform's core mission is radical transparency. Every correlation shown must be factual, statistically defensible, and link to its source data.

---

## The One Sentence That Drives All Architecture Decisions

> **The primary domain object is the Relationship between a donor and a representative** — not the transaction, not the representative, not the donor. A relationship has direction, history, weight, and behavioral consequence (voting).

---

## Tech Stack — Full Decisions

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js (TypeScript) | SSR for SEO, React for D3 viz, Vercel deploy |
| Internal API | GraphQL via Strawberry (Python) | Multi-hop queries in one round trip for network graph |
| Public API | REST via FastAPI | Stable, cacheable, auto-generates OpenAPI docs |
| Backend runtime | Python + FastAPI | Superior NLP, fuzzy matching, Celery ecosystem |
| Primary DB | PostgreSQL | Aggregates, rollups, time-series donation history |
| Graph DB | Neo4j Aura | Donor network traversal — `(donor)-[:FUNDED]->(rep)` |
| Job queue | Celery + Redis | Each pipeline stage scales independently |
| NLP | spaCy + keywords | Bill → industry classification |
| Entity resolution | rapidfuzz | Deduplicates "GOOGLE INC" / "GOOGLE LLC" → one entity |
| Type safety | openapi-typescript codegen | FastAPI spec → TypeScript types for Next.js |
| Hosting | Vercel (frontend) + Railway (backend) + Neo4j Aura | ~$0–20/month at launch |
| Deployment | Modular monolith → Docker Compose locally | One `docker-compose up` runs everything |

---

## Architecture Pattern: Hexagonal (Ports & Adapters)

Every bounded context follows this structure:

```
DRIVING SIDE              DOMAIN CORE                DRIVEN SIDE
(HTTP, GraphQL,    →    Pure Python only.     →    (Postgres, Neo4j,
 Celery triggers)       No ORM, no HTTP,            Redis, APIs)
                         no framework imports.
                         Only domain models.
        INPUT PORTS  ←─  domain defines  ─→  OUTPUT PORTS
        (interfaces)                          (interfaces)
              ↑                                     ↑
         ADAPTERS                              ADAPTERS
    (FastAPI routes)                    (PostgresRepo, Neo4jRepo,
                                         FECApiClient, spaCyNLP)
```

**The golden rule: the domain core never imports from sqlalchemy, httpx, fastapi, redis, or any framework. Ever.**

---

## Bounded Contexts (9 total)

| Context | Owns | Depends On | Key Models |
|---|---|---|---|
| **Ingestion** | Raw data exactly as received from APIs | — | `RawFiling`, `RawVote`, `RawDonor` |
| **Identity** | Canonical resolved entities | Ingestion (reads raw) | `CanonicalRep`, `CanonicalDonor` |
| **Finance** | Contributions, aggregates, industry rollups | Identity | `Contribution`, `DonorRepRelationship`, `IndustryRollup` |
| **Voting** | Bills, roll call votes, sponsorships | Identity | `Bill`, `RollCallVote`, `Sponsorship` |
| **Correlation** | Donor-vote alignment scores, before/after analysis | Finance + Voting + Identity | `CorrelationEvent`, `AlignmentScore` |
| **Discovery** | Search index, ZIP lookup, district map | Identity | `SearchResult`, `DistrictMap` |
| **Comparison** | Side-by-side rep analysis | Finance + Identity | `ComparisonReport`, `SharedDonor` |
| **Export/API** | Public REST endpoints, CSV/JSON | Finance + Voting + Correlation | `ExportJob`, `APIResponse` |
| **Embedding** | Embeddable widgets for third-party sites | Finance + Correlation | `WidgetConfig`, `WidgetPayload` |

**Contexts never share database tables. All cross-context communication goes through explicit service interfaces or domain events.**

---

## Core Domain Models (Pure Python — no framework imports)

```python
# domain/finance/models.py
@dataclass
class DonorRepRelationship:        # THE AGGREGATE ROOT
    id:              RelationshipId
    donor:           CanonicalDonorRef
    representative:  CanonicalRepRef
    contributions:   list[Contribution]
    first_donation:  date
    latest_donation: date
    total_amount:    Money
    cycles:          list[ElectionCycle]

# domain/correlation/models.py
@dataclass
class AlignmentScore:
    representative:  CanonicalRepRef
    donor:           CanonicalDonorRef
    industry:        Industry
    score:           float           # 0.0 – 1.0
    confidence:      ConfidenceLevel # LOW / MEDIUM / HIGH
    evidence_count:  int
    before_score:    float           # alignment BEFORE major donation
    after_score:     float           # alignment AFTER major donation
    shift:           float           # after - before (THE key signal)
    methodology_url: str             # always link to methodology

# domain/voting/models.py
@dataclass
class Bill:
    id:             BillId
    title:          str
    industries:     list[Industry]   # NLP-assigned
    nlp_confidence: float

@dataclass
class RollCallVote:
    bill:           BillRef
    representative: CanonicalRepRef
    position:       VotePosition     # YES / NO / ABSTAIN / NOT_VOTING
    voted_at:       datetime
    vote_type:      VoteType         # FLOOR / COMMITTEE
```

---

## Correlation Engine — Statistical Rules

A shift in voting alignment is only surfaced to users when ALL of the following are true:

1. `evidence_count >= 5` — minimum sample size (relevant votes in window)
2. `|shift| >= 0.15` — meaningful magnitude (15 point alignment change)
3. `p-value < 0.05` — Fisher's exact test for statistical significance
4. Before/after window = 24 months each side of the major donation event

**Every AlignmentScore must link to `methodology_url`. Correlation ≠ causation must be stated explicitly in the UI.**

---

## Data Pipeline

Runs nightly at 02:00 UTC via cron. Stages are connected by Celery + Redis queue.

```
Stage 1: INGESTION        — FEC API + Congress.gov API + Senate XML → raw tables (never mutated)
Stage 2: IDENTITY         — rapidfuzz deduplication → canonical entities
Stage 2: NLP CLASSIFY     — spaCy tags bills with industry categories
Stage 3: FINANCE ROLLUP   — aggregates → PostgreSQL materialized views + Neo4j
Stage 4: CORRELATION      — AlignmentScore computation per (rep, industry) pair
```

**Failure mode: FAIL LOUD.**
- Any stage failure → immediate alert (email + Slack webhook)
- Pipeline halts — downstream stages do not run on partial data
- Last successful data continues to be served
- Staleness banner shown on all pages with last-updated timestamp
- Auto-retry: 3 attempts with exponential backoff before human alert

---

## Data Sources

| Source | Used For | Cost |
|---|---|---|
| FEC API | Individual contributions, PAC donations | Free |
| OpenSecrets API | Industry categorization, dark money | Paid tier needed |
| Congress.gov API v3 | Roll call votes (House), bills, members | Free (key required) |
| Senate.gov XML feeds | Roll call votes (Senate), per-senator positions | Free (no key) |
| Google Civic Info API | ZIP code → district lookup | Free tier |
| Census TIGER Shapefiles | Congressional district boundaries for map | Free |

---

## Folder Structure

```
follow-the-money/
├── apps/
│   ├── web/                        # Next.js frontend (TypeScript)
│   │   ├── app/
│   │   │   ├── page.tsx            # Homepage (ZIP + map + search)
│   │   │   ├── rep/[id]/page.tsx   # Representative profile
│   │   │   ├── donor/[id]/page.tsx # Donor detail
│   │   │   └── compare/page.tsx    # Side-by-side comparison
│   │   ├── components/
│   │   │   ├── visualizations/     # D3 charts, network graph, map
│   │   │   ├── correlation/        # Timeline, heatmap, side-by-side viz
│   │   │   └── shared/             # Nav, cards, layout
│   │   └── lib/
│   │       ├── graphql/            # Apollo client + generated types
│   │       └── api/                # REST client + openapi-generated types
│   │
│   └── api/                        # Python FastAPI backend
│       ├── main.py                 # FastAPI app entry point
│       ├── graphql_schema.py       # Strawberry GraphQL schema
│       └── rest_router.py          # Public REST endpoints
│
├── domain/                         # PURE DOMAIN — zero framework imports
│   ├── shared/                     # Shared value objects
│   │   ├── money.py
│   │   ├── election_cycle.py
│   │   └── industry.py             # Industry enum + taxonomy
│   ├── identity/
│   │   ├── models.py               # CanonicalRep, CanonicalDonor
│   │   ├── ports.py                # IdentityRepository (abstract)
│   │   └── services.py             # EntityResolver
│   ├── finance/
│   │   ├── models.py               # Contribution, DonorRepRelationship
│   │   ├── ports.py                # FinanceRepository, FundingQueryPort
│   │   └── services.py             # FundingAggregationService
│   ├── voting/
│   │   ├── models.py               # Bill, RollCallVote, Sponsorship
│   │   ├── ports.py                # VotingRepository
│   │   └── services.py             # VotingRecordService
│   ├── correlation/
│   │   ├── models.py               # CorrelationEvent, AlignmentScore
│   │   ├── ports.py                # CorrelationRepository
│   │   ├── services.py             # CorrelationEngine
│   │   └── statistics.py           # Fisher exact test, shift detection
│   ├── discovery/
│   │   ├── models.py               # SearchResult, DistrictMap
│   │   ├── ports.py                # SearchPort, ZipLookupPort
│   │   └── services.py
│   ├── comparison/
│   │   ├── models.py               # ComparisonReport, SharedDonor
│   │   └── services.py
│   ├── export/
│   │   ├── models.py
│   │   └── services.py
│   └── embedding/
│       ├── models.py               # WidgetConfig, WidgetPayload
│       └── services.py
│
├── adapters/                       # Concrete implementations of ports
│   ├── postgres/
│   │   ├── finance_repo.py
│   │   ├── voting_repo.py
│   │   ├── correlation_repo.py
│   │   └── migrations/             # Alembic migrations
│   ├── neo4j/
│   │   ├── relationship_repo.py    # Donor-rep graph queries
│   │   └── network_query.py        # Multi-hop traversal
│   ├── external/
│   │   ├── fec_client.py
│   │   ├── congress_client.py
│   │   ├── senate_xml_client.py
│   │   └── opensecrets_client.py
│   └── nlp/
│       ├── bill_classifier.py      # spaCy bill → industry tagger
│       └── entity_resolver.py      # rapidfuzz donor deduplication
│
├── pipeline/                       # Celery tasks
│   ├── celery_app.py
│   ├── tasks/
│   │   ├── ingest_fec.py
│   │   ├── ingest_votes.py
│   │   ├── resolve_identities.py
│   │   ├── classify_bills.py
│   │   ├── aggregate_finance.py
│   │   └── compute_correlations.py
│   └── monitoring/
│       ├── health_check.py
│       └── staleness_tracker.py
│
├── infrastructure/
│   ├── docker/
│   │   ├── Dockerfile.api
│   │   ├── Dockerfile.worker
│   │   └── docker-compose.yml
│   └── scripts/
│       ├── seed_dev_data.py
│       └── backfill_correlations.py
│
├── docs/
│   ├── methodology.md              # Public correlation methodology page
│   ├── api/                        # Auto-generated from FastAPI
│   └── adr/                        # Architecture Decision Records
│       ├── 001-relationship-as-aggregate-root.md
│       ├── 002-modular-monolith.md
│       └── 003-correlation-statistics.md
│
└── CLAUDE.md                       # ← this file
```

---

## Local Dev — One Command

```bash
docker-compose up         # starts everything
# localhost:3000  → Next.js frontend
# localhost:8000  → FastAPI + GraphQL playground (/graphql)
# localhost:8000/docs → REST API auto-docs
# localhost:5432  → PostgreSQL
# localhost:6379  → Redis
# localhost:7474  → Neo4j Browser
# localhost:5555  → Flower (Celery monitor)

python infrastructure/scripts/seed_dev_data.py   # populate dev data
```

---

## GraphQL — Key Query Pattern

```graphql
# One query fetches everything the profile page needs
query RepProfile($id: ID!, $cycle: ElectionCycle!) {
  representative(id: $id) {
    name party chamber state
    fundingProfile(cycle: $cycle) { topIndustries topDonors total }
    correlations { donor industry score shift confidence evidenceCount }
    topDonors(limit: 10) { donor totalAmount industryCategory }
    votingRecord(from: "2022-01-01") { votes { bill position votedAt } }
  }
}
```

---

## Public REST API Endpoints

```
GET /v1/representatives              # list, supports ?state= &chamber= &party=
GET /v1/representatives/{id}         # full profile
GET /v1/representatives/{id}/votes   # voting record with industry tags
GET /v1/representatives/{id}/correlations  # alignment scores
GET /v1/donors/{id}                  # donor profile
GET /v1/donors/{id}/recipients       # all reps funded by donor
GET /v1/search?q={query}             # name search
GET /v1/zip/{zipcode}                # reps for ZIP code
GET /v1/compare?ids={id1},{id2}      # comparison report
GET /v1/export/{rep_id}.csv          # CSV export
```

---

## Sprint Build Order

| Sprint | Focus |
|---|---|
| 1 | Docker Compose · PostgreSQL schema · Neo4j connection · FastAPI skeleton · Next.js scaffold · codegen pipeline |
| 2 | FEC API adapter · Congress.gov API adapter · Senate XML adapter · Raw models · Celery pipeline Stage 1 · Fail-loud alerting |
| 3 | Donor entity resolver (rapidfuzz) · CanonicalRep/Donor · Identity resolution task |
| 4 | Contribution models · Finance aggregation · Materialized views · Neo4j graph · GraphQL queries |
| 5 | Homepage (ZIP + map + search) · Rep profile page · Donut + bar + treemap · Donor detail page |
| 6 | Neo4j multi-hop queries · D3 force-directed network viz · Donor → reps traversal |
| 7 | Bill detail enrichment (Congress.gov /bill + /subjects) · Bill models · spaCy NLP classifier · Voting record UI |
| 8 | CorrelationEngine statistics · AlignmentScore computation · Timeline + heatmap + side-by-side viz · Methodology page |
| 9 | Public REST API · CSV/JSON export · Embeddable widget · Shareable URLs · Comparison view · Performance |
| 10 | Full UI redesign — dark theme · Fixed nav with search · Interactive 50-state SVG map (click → /results?state=) · Dedicated /results page (handles ?q/?state/?chamber/?zip) · VizPanel tabs (Donut/Bar/Treemap/Network) · Sidebar (Funding Breakdown placeholder · Top Donors · Share & Export) · ZipForm · All 4 pages dark-themed |
| 11 | Implement placeholders — Small Donors (<$200) breakdown · Foreign-Connected PAC data · Export JSON endpoint (`GET /v1/export/{rep_id}.json`) · Live ticker feed (latest FEC filings endpoint) · Live aggregated stats (total donors · total raised · total correlations) · Mobile/tablet responsive layout |

---

## UX Principles (Non-Negotiable)

- **2-click rule**: No insight requires more than 2 clicks from the homepage
- **Click 1**: Find the representative (map, ZIP, search, or browse)
- **Click 2**: See their full funding profile
- **Desktop-first** at 1280px+, responsive down to tablet
- **Party colors**: Democrat `#1A4FD6` (blue) · Republican `#E63022` (red)
- **Correlation disclaimers**: Always visible. Correlation ≠ causation. Always link to methodology.

---

## How to Use This File in a New Session

Paste this prompt at the start of any new Claude conversation or Claude Code session:

```
Read CLAUDE.md in the project root. That file contains the full 
architecture for this project. We are on Sprint [N]. Today's task is: [task].
```

That's all you need. The architecture is fully encoded in this file.