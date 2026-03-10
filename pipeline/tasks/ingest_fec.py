"""
Stage 1a: Ingest FEC contribution data into raw tables.

Failure mode: FAIL LOUD.
- Max 3 retries with exponential backoff.
- After all retries exhausted → send alert and re-raise (halts pipeline).
- Last successful data continues to be served; staleness banner shown on frontend.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from ulid import ULID

from adapters.external.fec_client import FECApiClient, FECApiError
from domain.ingestion.models import RawFiling
from infrastructure.config import get_settings
from infrastructure.database import get_session
from pipeline.celery_app import celery_app
from pipeline.monitoring.alerting import send_pipeline_failure_alert, send_pipeline_success_alert
from pipeline.monitoring.staleness_tracker import StalenessTracker

logger = logging.getLogger(__name__)


@celery_app.task(
    name="pipeline.tasks.ingest_fec.run",
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # seconds; Celery doubles this on each retry (exponential)
)
def run(self) -> dict:
    """
    Fetch FEC Schedule A contributions for the current election cycle
    and upsert into the raw_filings table.

    Returns a summary dict: {"rows_written": N, "cycle": YYYY}.
    """
    settings = get_settings()
    cycle = settings.current_congress * 2 + 1787  # approximate — overridden by config
    # Use the configured election cycle directly from env
    cycle = _current_election_cycle(settings.current_congress)

    logger.info("ingest_fec: starting for election cycle %d", cycle)

    try:
        rows_written = _fetch_and_store(cycle)
    except FECApiError as exc:
        logger.error("ingest_fec: FEC API error on attempt %d: %s", self.request.retries + 1, exc)
        try:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            send_pipeline_failure_alert(
                "ingest_fec",
                exc,
                extra={"cycle": cycle, "retries": self.max_retries},
            )
            raise
    except Exception as exc:
        logger.exception("ingest_fec: unexpected error: %s", exc)
        try:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            send_pipeline_failure_alert(
                "ingest_fec",
                exc,
                extra={"cycle": cycle, "retries": self.max_retries},
            )
            raise

    StalenessTracker().record_success()
    send_pipeline_success_alert("ingest_fec", rows_written=rows_written)
    logger.info("ingest_fec: done — %d rows written", rows_written)
    return {"rows_written": rows_written, "cycle": cycle}


# ── Implementation ────────────────────────────────────────────────────────────


def _fetch_and_store(cycle: int) -> int:
    """
    Pull all contributions for the given election cycle from the FEC API
    and bulk-upsert into raw_filings.

    Returns the number of rows inserted (new) or updated (idempotent).
    """
    from adapters.postgres.orm_models import RawFilingRow
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    rows_written = 0

    committee_ids_seen: set[str] = set()

    with FECApiClient() as fec:
        with get_session() as session:
            batch: list[dict] = []

            for record in fec.get_contributions(two_year_transaction_period=cycle):
                filing = _map_to_domain(record)
                batch.append(_to_row_dict(filing))
                if filing.committee_id:
                    committee_ids_seen.add(filing.committee_id)

                if len(batch) >= 500:
                    rows_written += _upsert_batch(session, RawFilingRow, batch)
                    batch.clear()

            if batch:
                rows_written += _upsert_batch(session, RawFilingRow, batch)

        # Populate committee → candidate mapping for newly seen committee IDs
        if committee_ids_seen:
            _fetch_committee_candidates(fec, committee_ids_seen)

    return rows_written


def _fetch_committee_candidates(fec: FECApiClient, committee_ids: set[str]) -> None:
    """
    Look up each committee ID on the FEC API and store committee → candidate mapping.
    Skips committee IDs already in the database. Best-effort — failures are logged, not raised.
    """
    from adapters.postgres.orm_models import FecCommitteeCandidateRow
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    with get_session() as session:
        # Only fetch IDs we haven't seen before
        existing = {
            row.committee_id
            for row in session.query(FecCommitteeCandidateRow.committee_id).all()
        }
        new_ids = committee_ids - existing

    if not new_ids:
        return

    rows: list[dict] = []
    for cid in new_ids:
        try:
            committee = fec.get_committee(cid)
            candidate_ids = committee.get("candidate_ids") or []
            rows.append({
                "committee_id": cid,
                "fec_candidate_id": candidate_ids[0] if candidate_ids else None,
                "committee_name": committee.get("name"),
            })
        except Exception as exc:
            logger.warning("ingest_fec: could not fetch committee %s: %s", cid, exc)

    if not rows:
        return

    with get_session() as session:
        stmt = pg_insert(FecCommitteeCandidateRow).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["committee_id"])
        session.execute(stmt)
        session.commit()

    logger.info("ingest_fec: stored %d committee→candidate mappings", len(rows))


def _map_to_domain(record: dict) -> RawFiling:
    """Map a raw FEC API result dict to a RawFiling domain model."""
    amount_raw = record.get("contribution_receipt_amount") or 0
    return RawFiling(
        id=str(ULID()),
        source="fec_api",
        source_id=record.get("transaction_id", ""),
        committee_id=record.get("committee_id", ""),
        contributor_name=record.get("contributor_name", "") or "",
        contributor_employer=record.get("contributor_employer", "") or "",
        contributor_occupation=record.get("contributor_occupation", "") or "",
        contributor_state=record.get("contributor_state", "") or "",
        amount_cents=int(float(amount_raw) * 100),
        contribution_date=record.get("contribution_receipt_date", "") or "",
        election_cycle=record.get("two_year_transaction_period", 0) or 0,
        payload=record,
    )


def _to_row_dict(filing: RawFiling) -> dict:
    return {
        "id": filing.id,
        "source": filing.source,
        "source_id": filing.source_id,
        "committee_id": filing.committee_id,
        "contributor_name": filing.contributor_name,
        "contributor_employer": filing.contributor_employer,
        "contributor_occupation": filing.contributor_occupation,
        "contributor_state": filing.contributor_state,
        "amount_cents": filing.amount_cents,
        "contribution_date": filing.contribution_date,
        "election_cycle": filing.election_cycle,
        "payload": filing.payload,
        "fetched_at": filing.fetched_at,
        "is_processed": filing.is_processed,
    }


def _upsert_batch(session, model_class, batch: list[dict]) -> int:
    """
    Insert a batch of rows, ignoring conflicts on (source, source_id).
    Returns the number of rows inserted.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = pg_insert(model_class).values(batch)
    stmt = stmt.on_conflict_do_nothing(constraint="uq_raw_filings_source_source_id")
    result = session.execute(stmt)
    session.commit()
    return result.rowcount


def _current_election_cycle(congress: int) -> int:
    """
    Map a congress number to its FEC two_year_transaction_period.
    119th Congress (2025–2026) → cycle 2026.
    """
    return 1786 + (congress * 2)
