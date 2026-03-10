"""
Finance aggregation service — domain logic for building DonorRepRelationships.
"""

from __future__ import annotations

from domain.finance.models import Contribution, DonorRepRelationship, RelationshipId
from domain.finance.ports import FinanceRepository, FundingQueryPort
from domain.identity.models import CanonicalDonorRef, CanonicalRepRef, DonorId, RepId
from domain.shared.election_cycle import ElectionCycle
from domain.shared.money import Money


class FundingAggregationService:
    """Aggregates contribution data into DonorRepRelationships."""

    def __init__(self, repo: FinanceRepository, query: FundingQueryPort) -> None:
        self._repo = repo
        self._query = query

    def get_or_create_relationship(
        self,
        rel_id: RelationshipId,
        donor_ref: CanonicalDonorRef,
        rep_ref: CanonicalRepRef,
    ) -> DonorRepRelationship:
        """Return existing relationship or create a new empty one."""
        existing = self._repo.get_relationship(rel_id)
        if existing is not None:
            return existing
        return DonorRepRelationship(
            id=rel_id,
            donor=donor_ref,
            representative=rep_ref,
        )

    def get_top_donors_for_rep(
        self, rep_id: RepId, cycle: ElectionCycle, limit: int = 10
    ) -> list[DonorRepRelationship]:
        return self._query.get_top_donors(rep_id, cycle, limit)

    def get_top_industries_for_rep(
        self, rep_id: RepId, cycle: ElectionCycle
    ) -> list[dict]:
        """Returns list of {"industry": str, "total_cents": int} sorted descending."""
        return self._query.get_top_industries(rep_id, cycle)

    def total_funding_for_rep(
        self, rep_id: RepId, cycle: ElectionCycle | None = None
    ) -> Money:
        """Sum all contributions to a rep, optionally filtered by election cycle."""
        relationships = self._repo.find_relationships_for_rep(rep_id, cycle)
        total = Money(cents=0)
        for rel in relationships:
            total = total + rel.total_amount
        return total
