"""
Correlation engine — computes AlignmentScore for each (rep, industry) pair.

TODO Sprint 8: Implement CorrelationEngine.
"""

from __future__ import annotations

from domain.correlation.ports import CorrelationRepository
from domain.finance.ports import FinanceRepository
from domain.voting.ports import VotingRepository


class CorrelationEngine:
    def __init__(
        self,
        finance_repo: FinanceRepository,
        voting_repo: VotingRepository,
        correlation_repo: CorrelationRepository,
    ) -> None:
        self._finance = finance_repo
        self._voting = voting_repo
        self._correlation = correlation_repo

    # TODO Sprint 8: compute_for_rep, compute_all
