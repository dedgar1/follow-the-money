"""
PostgreSQL adapter for the Correlation repository port.

TODO Sprint 8: Implement all methods.
"""

from __future__ import annotations

from domain.correlation.models import AlignmentScore, CorrelationEvent
from domain.correlation.ports import CorrelationRepository
from domain.identity.models import RepId
from domain.shared.industry import Industry


class PostgresCorrelationRepository(CorrelationRepository):
    def save_score(self, score: AlignmentScore) -> None:
        raise NotImplementedError("TODO Sprint 8")

    def get_scores_for_rep(self, rep_id: RepId) -> list[AlignmentScore]:
        raise NotImplementedError("TODO Sprint 8")

    def get_scores_for_rep_industry(
        self, rep_id: RepId, industry: Industry
    ) -> list[AlignmentScore]:
        raise NotImplementedError("TODO Sprint 8")

    def save_event(self, event: CorrelationEvent) -> None:
        raise NotImplementedError("TODO Sprint 8")

    def get_events_for_rep(self, rep_id: RepId) -> list[CorrelationEvent]:
        raise NotImplementedError("TODO Sprint 8")
