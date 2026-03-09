"""
Voting context output ports.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from domain.identity.models import RepId
from domain.voting.models import Bill, BillId, RollCallVote, Sponsorship


class VotingRepository(ABC):
    @abstractmethod
    def get_bill(self, bill_id: BillId) -> Bill | None: ...

    @abstractmethod
    def save_bill(self, bill: Bill) -> None: ...

    @abstractmethod
    def get_votes_for_rep(
        self,
        rep_id: RepId,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[RollCallVote]: ...

    @abstractmethod
    def save_vote(self, vote: RollCallVote) -> None: ...

    @abstractmethod
    def get_sponsorships_for_rep(self, rep_id: RepId) -> list[Sponsorship]: ...
