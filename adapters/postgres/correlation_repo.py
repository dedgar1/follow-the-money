"""
PostgreSQL adapter for the Correlation repository port — Sprint 8.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from adapters.postgres.orm_models import AlignmentScoreRow, CorrelationEventRow
from domain.correlation.models import (
    AlignmentScore,
    AlignmentScoreId,
    ConfidenceLevel,
    CorrelationEvent,
    CorrelationEventId,
)
from domain.correlation.ports import CorrelationRepository
from domain.identity.models import CanonicalDonorRef, CanonicalRepRef, DonorId, RepId
from domain.shared.industry import Industry
from domain.shared.money import Money


class PostgresCorrelationRepository(CorrelationRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    # ── AlignmentScore ────────────────────────────────────────────────────────

    def save_score(self, score: AlignmentScore) -> None:
        """Upsert by (rep_id, industry) — re-running the pipeline overwrites."""
        row = (
            self._session.query(AlignmentScoreRow)
            .filter_by(
                rep_id=str(score.representative.id),
                industry=score.industry.value,
            )
            .first()
        )
        if row is None:
            row = AlignmentScoreRow(id=str(score.id))
            self._session.add(row)
        else:
            # Keep existing id; update the rest
            pass

        row.rep_id = str(score.representative.id)
        row.donor_id = str(score.donor.id)
        row.industry = score.industry.value
        row.score = score.score
        row.confidence = score.confidence.value
        row.evidence_count = score.evidence_count
        row.before_score = score.before_score
        row.after_score = score.after_score
        row.shift = score.shift
        row.p_value = score.p_value
        row.methodology_url = score.methodology_url
        row.computed_at = score.computed_at.isoformat() if score.computed_at else None
        self._session.flush()

    def get_scores_for_rep(self, rep_id: RepId) -> list[AlignmentScore]:
        rows = (
            self._session.query(AlignmentScoreRow)
            .filter_by(rep_id=str(rep_id))
            .all()
        )
        return [_score_from_row(r) for r in rows]

    def get_scores_for_rep_industry(
        self, rep_id: RepId, industry: Industry
    ) -> list[AlignmentScore]:
        rows = (
            self._session.query(AlignmentScoreRow)
            .filter_by(rep_id=str(rep_id), industry=industry.value)
            .all()
        )
        return [_score_from_row(r) for r in rows]

    # ── CorrelationEvent ──────────────────────────────────────────────────────

    def save_event(self, event: CorrelationEvent) -> None:
        row = self._session.get(CorrelationEventRow, str(event.id))
        if row is None:
            row = CorrelationEventRow(id=str(event.id))
            self._session.add(row)
        row.rep_id = str(event.representative.id)
        row.donor_id = str(event.donor.id)
        row.industry = event.industry.value
        row.event_date = event.event_date.isoformat()
        row.threshold_amount_cents = event.threshold_amount.cents
        self._session.flush()

    def get_events_for_rep(self, rep_id: RepId) -> list[CorrelationEvent]:
        rows = (
            self._session.query(CorrelationEventRow)
            .filter_by(rep_id=str(rep_id))
            .all()
        )
        return [_event_from_row(r) for r in rows]


# ── Row → domain model mappers ────────────────────────────────────────────────


def _score_from_row(row: AlignmentScoreRow) -> AlignmentScore:
    computed_at: date | None = None
    if row.computed_at:
        try:
            computed_at = date.fromisoformat(row.computed_at)
        except ValueError:
            pass

    return AlignmentScore(
        id=AlignmentScoreId(row.id),
        representative=CanonicalRepRef(id=RepId(row.rep_id), full_name=""),
        donor=CanonicalDonorRef(id=DonorId(row.donor_id), name=""),
        industry=Industry(row.industry),
        score=row.score,
        confidence=ConfidenceLevel(row.confidence),
        evidence_count=row.evidence_count,
        before_score=row.before_score,
        after_score=row.after_score,
        shift=row.shift,
        p_value=row.p_value,
        methodology_url=row.methodology_url,
        computed_at=computed_at,
    )


def _event_from_row(row: CorrelationEventRow) -> CorrelationEvent:
    return CorrelationEvent(
        id=CorrelationEventId(row.id),
        representative=CanonicalRepRef(id=RepId(row.rep_id), full_name=""),
        donor=CanonicalDonorRef(id=DonorId(row.donor_id), name=""),
        industry=Industry(row.industry),
        event_date=date.fromisoformat(row.event_date),
        threshold_amount=Money(cents=row.threshold_amount_cents),
    )
