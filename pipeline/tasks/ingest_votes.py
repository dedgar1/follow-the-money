"""
Stage 1b: Ingest roll-call vote data into raw_votes.

Sources:
  House  → Congress.gov API v3 (/house-vote endpoints, beta, 118th Congress+)
  Senate → Senate.gov XML feeds (no API key required)

Failure mode: FAIL LOUD — same retry/alert pattern as ingest_fec.
"""

from __future__ import annotations

import logging

from ulid import ULID

from adapters.external.congress_client import CongressApiError, CongressGovClient
from adapters.external.senate_xml_client import SenateXmlClient, SenateXmlError
from domain.ingestion.models import RawVote
from infrastructure.config import get_settings
from infrastructure.database import get_session
from pipeline.celery_app import celery_app
from pipeline.monitoring.alerting import send_pipeline_failure_alert, send_pipeline_success_alert
from pipeline.monitoring.staleness_tracker import StalenessTracker

logger = logging.getLogger(__name__)


@celery_app.task(
    name="pipeline.tasks.ingest_votes.run",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run(self) -> dict:
    """
    Fetch roll-call votes for both chambers and upsert into raw_votes.

    Returns {"rows_written": N, "congress": N, "session": N}.
    """
    settings = get_settings()
    congress = settings.current_congress
    session_num = settings.current_session

    logger.info("ingest_votes: starting for %dth Congress session %d", congress, session_num)

    try:
        house_rows = _ingest_house(congress, session_num)
        senate_rows = _ingest_senate(congress, session_num)
        rows_written = house_rows + senate_rows
    except (CongressApiError, SenateXmlError) as exc:
        logger.error("ingest_votes: error on attempt %d: %s", self.request.retries + 1, exc)
        try:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            send_pipeline_failure_alert(
                "ingest_votes", exc,
                extra={"congress": congress, "session": session_num},
            )
            raise
    except Exception as exc:
        logger.exception("ingest_votes: unexpected error: %s", exc)
        try:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            send_pipeline_failure_alert(
                "ingest_votes", exc,
                extra={"congress": congress, "session": session_num},
            )
            raise

    StalenessTracker().record_success()
    send_pipeline_success_alert("ingest_votes", rows_written=rows_written)
    logger.info("ingest_votes: done — %d rows written (%d house, %d senate)",
                rows_written, house_rows, senate_rows)
    return {"rows_written": rows_written, "congress": congress, "session": session_num}


# ── House ─────────────────────────────────────────────────────────────────────


def _ingest_house(congress: int, session_num: int) -> int:
    """Fetch House votes via Congress.gov API and upsert into raw_votes."""
    rows_written = 0

    with CongressGovClient() as api:
        with get_session() as db:
            batch: list[dict] = []

            for vote_summary in api.get_house_votes(congress, session_num):
                roll_call = vote_summary.get("rollCallNumber", 0)
                vote_date = vote_summary.get("startDate", "")
                # Bill info is flat on the summary (not nested)
                bill_info = {
                    "number": vote_summary.get("legislationNumber", ""),
                    "type": vote_summary.get("legislationType", ""),
                    "title": "",  # not in summary; fetched separately if needed
                    "url": vote_summary.get("legislationUrl", ""),
                }

                try:
                    members = api.get_house_vote_members(congress, session_num, roll_call)
                except CongressApiError as exc:
                    logger.warning("ingest_votes: skipping House vote %d: %s", roll_call, exc)
                    continue

                source_id = f"house/{congress}/{session_num}/{roll_call}"

                for member in members:
                    raw_vote = _map_house_member(
                        member,
                        vote_summary=vote_summary,
                        bill_info=bill_info,
                        congress=congress,
                        session_num=session_num,
                        roll_call=roll_call,
                        vote_date=vote_date,
                        source_id=source_id,
                    )
                    batch.append(_to_row_dict(raw_vote))

                    if len(batch) >= 500:
                        rows_written += _upsert_batch(db, batch)
                        batch.clear()

            if batch:
                rows_written += _upsert_batch(db, batch)

    return rows_written


def _map_house_member(
    member: dict,
    *,
    vote_summary: dict,
    bill_info: dict,
    congress: int,
    session_num: int,
    roll_call: int,
    vote_date: str,
    source_id: str,
) -> RawVote:
    first = member.get("firstName", "")
    last = member.get("lastName", "")
    full_name = f"{first} {last}".strip()
    return RawVote(
        id=str(ULID()),
        source="congress_api",
        source_id=source_id,
        congress=congress,
        session=session_num,
        chamber="House",
        roll_call=roll_call,
        bill_id=bill_info.get("number", ""),
        bill_title=bill_info.get("title", ""),
        member_bioguide_id=member.get("bioguideID", ""),
        member_name=full_name,
        position=member.get("voteCast", ""),
        voted_at=vote_date[:10] if vote_date else "",
        payload={
            "member": member,
            "vote_summary": vote_summary,
            "bill": bill_info,
        },
    )


# ── Senate ────────────────────────────────────────────────────────────────────


def _ingest_senate(congress: int, session_num: int) -> int:
    """Fetch Senate votes from Senate.gov XML and upsert into raw_votes."""
    rows_written = 0

    with SenateXmlClient() as senate:
        with get_session() as db:
            batch: list[dict] = []

            for vote_detail in senate.get_all_vote_details(congress, session_num):
                roll_call = vote_detail["roll_call"]
                source_id = f"senate/{congress}/{session_num}/{roll_call}"

                for member in vote_detail.get("members", []):
                    raw_vote = _map_senate_member(
                        member,
                        vote_detail=vote_detail,
                        congress=congress,
                        session_num=session_num,
                        roll_call=roll_call,
                        source_id=source_id,
                    )
                    batch.append(_to_row_dict(raw_vote))

                    if len(batch) >= 500:
                        rows_written += _upsert_batch(db, batch)
                        batch.clear()

            if batch:
                rows_written += _upsert_batch(db, batch)

    return rows_written


def _map_senate_member(
    member: dict,
    *,
    vote_detail: dict,
    congress: int,
    session_num: int,
    roll_call: int,
    source_id: str,
) -> RawVote:
    # Senate XML uses lis_member_id, not bioguide_id.
    # Store lis_member_id in member_bioguide_id for now; identity resolution
    # (Sprint 3) will map it to the canonical bioguide_id via the members table.
    return RawVote(
        id=str(ULID()),
        source="senate_xml",
        source_id=source_id,
        congress=congress,
        session=session_num,
        chamber="Senate",
        roll_call=roll_call,
        bill_id=vote_detail.get("bill_id", ""),
        bill_title=vote_detail.get("bill_title", ""),
        member_bioguide_id=member.get("lis_member_id", ""),  # resolved in Sprint 3
        member_name=member.get("member_full", ""),
        position=member.get("vote_cast", ""),
        voted_at=_normalize_senate_date(vote_detail.get("vote_date", ""), congress),
        payload={
            "member": member,
            "vote_detail": {k: v for k, v in vote_detail.items() if k != "members"},
        },
    )


def _normalize_senate_date(raw_date: str, congress: int) -> str:
    """
    Senate XML dates are 'DD-Mon' (e.g. '18-Dec') without a year.
    Derive the year from the congress number (119th → 2025 or 2026).
    Returns 'YYYY-MM-DD' or the raw string if parsing fails.
    """
    import datetime

    if not raw_date or len(raw_date) < 6:
        return raw_date

    # 119th Congress: Jan 2025 – Jan 2027. Use start year as base.
    start_year = 1787 + (congress * 2)  # 119 → 2025

    try:
        # Try to parse 'DD-Mon'; assume start_year first, then +1 if month < Jan
        dt = datetime.datetime.strptime(f"{raw_date}-{start_year}", "%d-%b-%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return raw_date


# ── Shared helpers ────────────────────────────────────────────────────────────


def _to_row_dict(vote: RawVote) -> dict:
    return {
        "id": vote.id,
        "source": vote.source,
        "source_id": vote.source_id,
        "congress": vote.congress,
        "session": vote.session,
        "chamber": vote.chamber,
        "roll_call": vote.roll_call,
        "bill_id": vote.bill_id,
        "bill_title": vote.bill_title,
        "member_bioguide_id": vote.member_bioguide_id,
        "member_name": vote.member_name,
        "position": vote.position,
        "voted_at": vote.voted_at,
        "payload": vote.payload,
        "fetched_at": vote.fetched_at,
        "is_processed": vote.is_processed,
    }


def _upsert_batch(session, batch: list[dict]) -> int:
    from adapters.postgres.orm_models import RawVoteRow
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = pg_insert(RawVoteRow).values(batch)
    stmt = stmt.on_conflict_do_nothing(constraint="uq_raw_votes_source_member")
    result = session.execute(stmt)
    session.commit()
    return result.rowcount
