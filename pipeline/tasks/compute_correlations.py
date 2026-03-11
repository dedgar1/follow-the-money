"""
Stage 4: Compute AlignmentScore for each (rep, industry) pair.

Steps:
  1. Load all canonical reps.
  2. For each rep, load their canonical relationships (with donor industry).
  3. Load all votes for this rep joined with bill industry tags.
  4. Run CorrelationEngine.compute_for_rep().
  5. Save significant AlignmentScores → alignment_scores table.

Failure mode: FAIL LOUD — same retry/alert pattern as other pipeline stages.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from pipeline.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="pipeline.tasks.compute_correlations.run",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run(self) -> dict:
    """Compute AlignmentScores for all canonical representatives."""
    logger.info("compute_correlations: starting")

    try:
        scores_written = _compute_all()
    except Exception as exc:
        logger.exception(
            "compute_correlations: error on attempt %d: %s",
            self.request.retries + 1,
            exc,
        )
        try:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            from pipeline.monitoring.alerting import send_pipeline_failure_alert
            send_pipeline_failure_alert("compute_correlations", exc)
            raise

    from pipeline.monitoring.alerting import send_pipeline_success_alert
    from pipeline.monitoring.staleness_tracker import StalenessTracker

    StalenessTracker().record_success()
    send_pipeline_success_alert("compute_correlations", rows_written=scores_written)
    logger.info("compute_correlations: done — %d scores written", scores_written)
    return {"scores_written": scores_written}


# ── Implementation ────────────────────────────────────────────────────────────


def _compute_all() -> int:
    """
    Core logic: iterate canonical reps, compute scores, persist.
    Returns total AlignmentScore rows written.
    """
    from adapters.postgres.orm_models import CanonicalRepRow
    from infrastructure.database import get_session

    with get_session() as session:
        reps = session.query(CanonicalRepRow).all()

    logger.info("compute_correlations: processing %d canonical reps", len(reps))

    total = 0
    for rep_row in reps:
        scores_written = _compute_for_rep(rep_row)
        total += scores_written

    return total


def _compute_for_rep(rep_row) -> int:
    """
    Compute and save AlignmentScores for one representative.
    Returns number of scores persisted.
    """
    from adapters.postgres.correlation_repo import PostgresCorrelationRepository
    from adapters.postgres.orm_models import CanonicalDonorRow, CanonicalRelationshipRow
    from domain.correlation.services import CorrelationEngine
    from domain.finance.models import DonorRepRelationship, RelationshipId
    from domain.identity.models import (
        CanonicalDonorRef,
        CanonicalRepRef,
        DonorId,
        RepId,
    )
    from domain.shared.election_cycle import ElectionCycle
    from domain.shared.industry import Industry
    from domain.shared.money import Money
    from domain.voting.models import BillRef, BillId, RollCallVote, VoteId, VotePosition, VoteType
    from infrastructure.database import get_session
    from sqlalchemy import text

    # We need stub ports to instantiate CorrelationEngine — the engine's
    # compute_for_rep() method takes explicit data so repos are not called.
    class _NullFinanceRepo:
        def get_relationship(self, *a): ...
        def save_relationship(self, *a): ...
        def find_relationships_for_rep(self, *a): return []
        def find_relationships_for_donor(self, *a): return []

    class _NullVotingRepo:
        def get_bill(self, *a): ...
        def save_bill(self, *a): ...
        def get_votes_for_rep(self, *a): return []
        def save_vote(self, *a): ...
        def get_sponsorships_for_rep(self, *a): return []

    class _NullCorrRepo:
        def save_score(self, *a): ...
        def get_scores_for_rep(self, *a): return []
        def get_scores_for_rep_industry(self, *a): return []
        def save_event(self, *a): ...
        def get_events_for_rep(self, *a): return []

    engine = CorrelationEngine(
        finance_repo=_NullFinanceRepo(),  # type: ignore[arg-type]
        voting_repo=_NullVotingRepo(),    # type: ignore[arg-type]
        correlation_repo=_NullCorrRepo(), # type: ignore[arg-type]
    )

    rep_id = RepId(rep_row.id)
    rep_ref = CanonicalRepRef(id=rep_id, full_name=rep_row.full_name)

    with get_session() as session:
        # ── 1. Load relationships with donor industry ─────────────────────────
        rel_rows = (
            session.query(CanonicalRelationshipRow)
            .filter_by(rep_id=rep_row.id)
            .all()
        )

        if not rel_rows:
            return 0

        # Load donor industry for each relationship
        donor_ids = [r.donor_id for r in rel_rows]
        donors = {
            d.id: d
            for d in session.query(CanonicalDonorRow)
            .filter(CanonicalDonorRow.id.in_(donor_ids))
            .all()
        }

        industry_relationships: list[tuple[DonorRepRelationship, Industry | None]] = []
        for r in rel_rows:
            from domain.shared.election_cycle import ElectionCycle
            import json as _json
            from datetime import date as _date

            cycles_raw: list[int] = _json.loads(r.election_cycles or "[]")

            rel = DonorRepRelationship(
                id=RelationshipId(r.id),
                donor=CanonicalDonorRef(id=DonorId(r.donor_id), name=""),
                representative=rep_ref,
                first_donation=_date.fromisoformat(r.first_donation_date) if r.first_donation_date else None,
                latest_donation=_date.fromisoformat(r.latest_donation_date) if r.latest_donation_date else None,
                total_amount=Money(cents=r.total_amount_cents),
                cycles=[ElectionCycle(year=y) for y in cycles_raw],
            )

            donor_row = donors.get(r.donor_id)
            industry: Industry | None = None
            if donor_row and donor_row.industry:
                try:
                    industry = Industry(donor_row.industry)
                except ValueError:
                    pass

            industry_relationships.append((rel, industry))

        # ── 2. Load votes with bill industry tags ─────────────────────────────
        if not rep_row.bioguide_id:
            return 0

        vote_rows = session.execute(
            text("""
                SELECT rv.id, rv.bill_id, rv.bill_title, rv.position,
                       rv.voted_at, rv.chamber,
                       b.industries
                FROM raw_votes rv
                LEFT JOIN bills b ON b.congress_gov_id = rv.bill_id
                WHERE rv.member_bioguide_id = :bioguide_id
            """),
            {"bioguide_id": rep_row.bioguide_id},
        ).fetchall()

        _POSITION_MAP = {
            "Yea": VotePosition.YES, "Yes": VotePosition.YES, "AYE": VotePosition.YES,
            "Nay": VotePosition.NO,  "No": VotePosition.NO,   "NAY": VotePosition.NO,
            "Not Voting": VotePosition.NOT_VOTING,
            "Present": VotePosition.ABSTAIN, "Abstain": VotePosition.ABSTAIN,
        }

        tagged_votes: list[tuple[RollCallVote, list[Industry]]] = []
        for row in vote_rows:
            try:
                industries_raw: list[str] = json.loads(row[6] or "[]")
            except (json.JSONDecodeError, TypeError):
                industries_raw = []

            industries: list[Industry] = []
            for v in industries_raw:
                try:
                    industries.append(Industry(v))
                except ValueError:
                    pass

            voted_at_str = str(row[4])[:10] if row[4] else ""
            try:
                voted_at = datetime.strptime(voted_at_str, "%Y-%m-%d")
            except ValueError:
                continue

            position = _POSITION_MAP.get(str(row[3]), VotePosition.NOT_VOTING)
            vote = RollCallVote(
                id=VoteId(str(row[0])),
                bill=BillRef(id=BillId(str(row[1] or "")), title=str(row[2] or "")),
                representative=rep_ref,
                position=position,
                voted_at=voted_at,
                vote_type=VoteType.FLOOR,
            )
            tagged_votes.append((vote, industries))

        # ── 3. Run engine ─────────────────────────────────────────────────────
        scores = engine.compute_for_rep(
            rep_ref=rep_ref,
            industry_relationships=industry_relationships,
            tagged_votes=tagged_votes,
        )

        if not scores:
            return 0

        # ── 4. Persist scores ─────────────────────────────────────────────────
        repo = PostgresCorrelationRepository(session)
        for score in scores:
            repo.save_score(score)
        session.commit()

        logger.info(
            "compute_correlations: %s — %d significant scores",
            rep_row.full_name,
            len(scores),
        )
        return len(scores)
