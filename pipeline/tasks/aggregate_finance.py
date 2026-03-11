"""
Stage 3: Aggregate canonical contributions → DonorRepRelationships + Neo4j graph.

Steps:
  1. Load committee → candidate mapping (fec_committee_candidates table).
  2. Load canonical reps indexed by fec_candidate_id.
  3. Load processed raw_filings with canonical_donor_id set.
  4. Build DonorRepRelationship aggregates per (canonical_donor, canonical_rep) pair.
  5. Upsert aggregates into canonical_donor_rep_relationships (PostgreSQL).
  6. Upsert nodes and FUNDED edges into Neo4j.

Failure mode: FAIL LOUD — same retry/alert pattern as ingest tasks.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import date
from typing import NamedTuple

from ulid import ULID

from adapters.neo4j.relationship_repo import Neo4jRelationshipRepo
from adapters.postgres.finance_repo import PostgresFinanceRepository
from adapters.postgres.orm_models import (
    CanonicalDonorRow,
    CanonicalRelationshipRow,
    CanonicalRepRow,
    FecCommitteeCandidateRow,
    RawFilingRow,
)
from domain.finance.models import DonorRepRelationship, RelationshipId
from domain.identity.models import CanonicalDonorRef, CanonicalRepRef, DonorId, RepId
from domain.shared.election_cycle import ElectionCycle
from domain.shared.money import Money
from infrastructure.database import get_session
from pipeline.celery_app import celery_app
from pipeline.monitoring.alerting import send_pipeline_failure_alert, send_pipeline_success_alert
from pipeline.monitoring.staleness_tracker import StalenessTracker

logger = logging.getLogger(__name__)


@celery_app.task(
    name="pipeline.tasks.aggregate_finance.run",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run(self) -> dict:
    """
    Aggregate canonical contributions into DonorRepRelationships.

    Returns {"relationships_written": N, "neo4j_edges_written": N}.
    """
    logger.info("aggregate_finance: starting")

    try:
        relationships_written, neo4j_edges = _aggregate()
    except Exception as exc:
        logger.exception("aggregate_finance: error on attempt %d: %s", self.request.retries + 1, exc)
        try:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            send_pipeline_failure_alert("aggregate_finance", exc)
            raise

    StalenessTracker().record_success()
    send_pipeline_success_alert("aggregate_finance", rows_written=relationships_written)
    logger.info(
        "aggregate_finance: done — %d relationships, %d Neo4j edges",
        relationships_written, neo4j_edges,
    )
    return {"relationships_written": relationships_written, "neo4j_edges_written": neo4j_edges}


# ── Implementation ────────────────────────────────────────────────────────────


def _aggregate() -> tuple[int, int]:
    """
    Core aggregation logic.
    Returns (relationships_written, neo4j_edges_written).
    """
    # Step 1: Load committee → candidate_id map
    committee_candidate_map = _load_committee_candidate_map()
    logger.info("aggregate_finance: loaded %d committee→candidate mappings", len(committee_candidate_map))

    # Step 2: Load canonical reps indexed by fec_candidate_id
    reps_by_fec_id, reps_by_id = _load_canonical_reps()
    logger.info("aggregate_finance: loaded %d canonical reps", len(reps_by_id))

    # Step 3: Load all processed filings that have a canonical_donor_id
    filings = _load_linked_filings()
    logger.info("aggregate_finance: processing %d linked filings", len(filings))

    if not filings:
        return 0, 0

    # Step 4: Load canonical donors for name resolution in the aggregate
    donors_by_id = _load_canonical_donors()

    # Step 5: Build aggregates in memory
    # Key: (canonical_donor_id, canonical_rep_id) → accumulated data
    AggKey = tuple[str, str]
    agg: dict[AggKey, dict] = {}

    unlinked = 0
    for filing in filings:
        donor_id: str = filing.canonical_donor_id  # type: ignore[assignment]
        if not donor_id:
            unlinked += 1
            continue

        candidate_id = committee_candidate_map.get(filing.committee_id or "")
        if not candidate_id:
            unlinked += 1
            continue

        rep_row = reps_by_fec_id.get(candidate_id)
        if not rep_row:
            unlinked += 1
            continue

        key: AggKey = (donor_id, rep_row.id)
        if key not in agg:
            agg[key] = {
                "donor_id": donor_id,
                "rep_id": rep_row.id,
                "total_cents": 0,
                "count": 0,
                "first_date": None,
                "latest_date": None,
                "cycles": set(),
            }

        entry = agg[key]
        entry["total_cents"] += filing.amount_cents or 0
        entry["count"] += 1

        if filing.contribution_date:
            try:
                d = date.fromisoformat(filing.contribution_date)
                if entry["first_date"] is None or d < entry["first_date"]:
                    entry["first_date"] = d
                if entry["latest_date"] is None or d > entry["latest_date"]:
                    entry["latest_date"] = d
            except ValueError:
                pass

        if filing.election_cycle:
            entry["cycles"].add(filing.election_cycle)

    if unlinked:
        logger.info("aggregate_finance: %d filings had no committee→rep mapping (expected for PACs)", unlinked)

    logger.info("aggregate_finance: built %d (donor, rep) aggregate pairs", len(agg))

    # Step 6: Upsert to PostgreSQL
    relationships_written = _upsert_relationships(agg)

    # Step 7: Upsert to Neo4j
    neo4j_edges = _write_neo4j_graph(agg, donors_by_id, reps_by_id)

    return relationships_written, neo4j_edges


def _load_committee_candidate_map() -> dict[str, str]:
    """committee_id → fec_candidate_id (only rows with a candidate set)."""
    with get_session() as session:
        rows = session.query(FecCommitteeCandidateRow).filter(
            FecCommitteeCandidateRow.fec_candidate_id.isnot(None)
        ).all()
        return {r.committee_id: r.fec_candidate_id for r in rows}  # type: ignore[misc]


def _load_canonical_reps() -> tuple[dict[str, CanonicalRepRow], dict[str, CanonicalRepRow]]:
    """Returns (by_fec_candidate_id, by_id)."""
    with get_session() as session:
        rows = session.query(CanonicalRepRow).all()
        by_fec: dict[str, CanonicalRepRow] = {}
        by_id: dict[str, CanonicalRepRow] = {}
        for r in rows:
            by_id[r.id] = r
            if r.fec_candidate_id:
                by_fec[r.fec_candidate_id] = r
        return by_fec, by_id


class _FilingData(NamedTuple):
    canonical_donor_id: str
    committee_id: str | None
    amount_cents: int | None
    contribution_date: str | None
    election_cycle: int | None


def _load_linked_filings() -> list[_FilingData]:
    """
    Return needed columns from processed filings that have a canonical_donor_id.
    Uses a plain SQL projection so the data survives session close (no detached-instance risk).
    """
    from sqlalchemy import text

    with get_session() as session:
        rows = session.execute(
            text(
                "SELECT canonical_donor_id, committee_id, amount_cents, "
                "       contribution_date, election_cycle "
                "FROM raw_filings "
                "WHERE is_processed = TRUE AND canonical_donor_id IS NOT NULL"
            )
        ).fetchall()
        return [_FilingData(*r) for r in rows]


def _load_canonical_donors() -> dict[str, CanonicalDonorRow]:
    with get_session() as session:
        rows = session.query(CanonicalDonorRow).all()
        return {r.id: r for r in rows}


def _upsert_relationships(agg: dict) -> int:
    """
    Upsert each aggregate entry into canonical_donor_rep_relationships.
    Returns number of rows written.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    rows = []
    for entry in agg.values():
        rows.append({
            "id": str(ULID()),
            "donor_id": entry["donor_id"],
            "rep_id": entry["rep_id"],
            "total_amount_cents": entry["total_cents"],
            "contribution_count": entry["count"],
            "first_donation_date": entry["first_date"].isoformat() if entry["first_date"] else None,
            "latest_donation_date": entry["latest_date"].isoformat() if entry["latest_date"] else None,
            "election_cycles": json.dumps(sorted(entry["cycles"])),
        })

    if not rows:
        return 0

    with get_session() as session:
        stmt = pg_insert(CanonicalRelationshipRow).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=None,
            constraint="uq_canonical_rel_donor_rep",
            set_={
                "total_amount_cents": stmt.excluded.total_amount_cents,
                "contribution_count": stmt.excluded.contribution_count,
                "first_donation_date": stmt.excluded.first_donation_date,
                "latest_donation_date": stmt.excluded.latest_donation_date,
                "election_cycles": stmt.excluded.election_cycles,
            },
        )
        result = session.execute(stmt)
        session.commit()
        return result.rowcount


def _write_neo4j_graph(
    agg: dict,
    donors_by_id: dict[str, CanonicalDonorRow],
    reps_by_id: dict[str, CanonicalRepRow],
) -> int:
    """
    Write canonical rep/donor nodes and FUNDED edges to Neo4j.
    Returns number of FUNDED edges written.
    """
    neo4j = Neo4jRelationshipRepo()
    edges_written = 0

    # Upsert all rep nodes involved
    rep_ids_needed = {entry["rep_id"] for entry in agg.values()}
    for rid in rep_ids_needed:
        rep = reps_by_id.get(rid)
        if rep:
            neo4j.upsert_rep_node(
                rep_id=rep.id,
                bioguide_id=rep.bioguide_id,
                full_name=rep.full_name,
                party=rep.party,
                chamber=rep.chamber,
                state=rep.state,
            )

    # Upsert all donor nodes involved
    donor_ids_needed = {entry["donor_id"] for entry in agg.values()}
    for did in donor_ids_needed:
        donor = donors_by_id.get(did)
        if donor:
            neo4j.upsert_donor_node(
                donor_id=donor.id,
                name=donor.name,
                donor_type=donor.donor_type,
            )

    # Upsert FUNDED edges
    for entry in agg.values():
        try:
            neo4j.upsert_funded_relationship(
                donor_id=entry["donor_id"],
                rep_id=entry["rep_id"],
                total_cents=entry["total_cents"],
                cycles=sorted(entry["cycles"]),
            )
            edges_written += 1
        except Exception as exc:
            logger.warning(
                "aggregate_finance: Neo4j edge write failed (%s→%s): %s",
                entry["donor_id"], entry["rep_id"], exc,
            )

    return edges_written
