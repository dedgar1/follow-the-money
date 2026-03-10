"""
Finance context output ports.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.finance.models import DonorRepRelationship, RelationshipId
from domain.identity.models import DonorId, RepId
from domain.shared.election_cycle import ElectionCycle


class FinanceRepository(ABC):
    @abstractmethod
    def get_relationship(self, rel_id: RelationshipId) -> DonorRepRelationship | None: ...

    @abstractmethod
    def save_relationship(self, rel: DonorRepRelationship) -> None: ...

    @abstractmethod
    def find_relationships_for_rep(
        self, rep_id: RepId, cycle: ElectionCycle | None = None
    ) -> list[DonorRepRelationship]: ...

    @abstractmethod
    def find_relationships_for_donor(
        self, donor_id: DonorId
    ) -> list[DonorRepRelationship]: ...


class FundingQueryPort(ABC):
    @abstractmethod
    def get_top_donors(
        self, rep_id: RepId, cycle: ElectionCycle, limit: int = 10
    ) -> list[DonorRepRelationship]: ...

    @abstractmethod
    def get_top_industries(self, rep_id: RepId, cycle: ElectionCycle) -> list[dict]: ...
