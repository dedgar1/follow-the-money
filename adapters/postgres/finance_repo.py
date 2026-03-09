"""
PostgreSQL adapter for the Finance repository port.

TODO Sprint 4: Implement all methods.
"""

from __future__ import annotations

from domain.finance.models import DonorRepRelationship, RelationshipId
from domain.finance.ports import FinanceRepository, FundingQueryPort
from domain.identity.models import DonorId, RepId
from domain.shared.election_cycle import ElectionCycle


class PostgresFinanceRepository(FinanceRepository):
    def get_relationship(self, rel_id: RelationshipId) -> DonorRepRelationship | None:
        raise NotImplementedError("TODO Sprint 4")

    def save_relationship(self, rel: DonorRepRelationship) -> None:
        raise NotImplementedError("TODO Sprint 4")

    def find_relationships_for_rep(
        self, rep_id: RepId, cycle: ElectionCycle | None = None
    ) -> list[DonorRepRelationship]:
        raise NotImplementedError("TODO Sprint 4")

    def find_relationships_for_donor(
        self, donor_id: DonorId
    ) -> list[DonorRepRelationship]:
        raise NotImplementedError("TODO Sprint 4")


class PostgresFundingQueryPort(FundingQueryPort):
    def get_top_donors(
        self, rep_id: RepId, cycle: ElectionCycle, limit: int = 10
    ) -> list[DonorRepRelationship]:
        raise NotImplementedError("TODO Sprint 4")

    def get_top_industries(self, rep_id: RepId, cycle: ElectionCycle) -> list[dict]:
        raise NotImplementedError("TODO Sprint 4")
