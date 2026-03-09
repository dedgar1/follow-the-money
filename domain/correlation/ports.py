"""
Correlation context output ports.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.correlation.models import AlignmentScore, CorrelationEvent
from domain.identity.models import DonorId, RepId
from domain.shared.industry import Industry


class CorrelationRepository(ABC):
    @abstractmethod
    def save_score(self, score: AlignmentScore) -> None: ...

    @abstractmethod
    def get_scores_for_rep(self, rep_id: RepId) -> list[AlignmentScore]: ...

    @abstractmethod
    def get_scores_for_rep_industry(
        self, rep_id: RepId, industry: Industry
    ) -> list[AlignmentScore]: ...

    @abstractmethod
    def save_event(self, event: CorrelationEvent) -> None: ...

    @abstractmethod
    def get_events_for_rep(self, rep_id: RepId) -> list[CorrelationEvent]: ...
