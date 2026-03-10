"""
Finance aggregation service.

TODO Sprint 4: Implement FundingAggregationService.
"""

from __future__ import annotations

from domain.finance.ports import FinanceRepository, FundingQueryPort


class FundingAggregationService:
    """Aggregates contribution data into DonorRepRelationships."""

    def __init__(self, repo: FinanceRepository, query: FundingQueryPort) -> None:
        self._repo = repo
        self._query = query

    # TODO Sprint 4: aggregate_for_rep, aggregate_industry_rollup
