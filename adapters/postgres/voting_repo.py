"""
PostgreSQL adapter for the Voting repository port.

TODO Sprint 7: Implement all methods.
"""

from __future__ import annotations

from datetime import datetime

from domain.identity.models import RepId
from domain.voting.models import Bill, BillId, RollCallVote, Sponsorship
from domain.voting.ports import VotingRepository


class PostgresVotingRepository(VotingRepository):
    def get_bill(self, bill_id: BillId) -> Bill | None:
        raise NotImplementedError("TODO Sprint 7")

    def save_bill(self, bill: Bill) -> None:
        raise NotImplementedError("TODO Sprint 7")

    def get_votes_for_rep(
        self,
        rep_id: RepId,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[RollCallVote]:
        raise NotImplementedError("TODO Sprint 7")

    def save_vote(self, vote: RollCallVote) -> None:
        raise NotImplementedError("TODO Sprint 7")

    def get_sponsorships_for_rep(self, rep_id: RepId) -> list[Sponsorship]:
        raise NotImplementedError("TODO Sprint 7")
