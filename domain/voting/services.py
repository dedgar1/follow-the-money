"""
Voting record service — Sprint 7.
"""

from __future__ import annotations

from datetime import datetime

from domain.identity.models import RepId
from domain.shared.industry import Industry
from domain.voting.models import RollCallVote
from domain.voting.ports import VotingRepository


class VotingRecordService:
    def __init__(self, repo: VotingRepository) -> None:
        self._repo = repo

    def get_record_for_rep(
        self,
        rep_id: RepId,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[RollCallVote]:
        """Return all roll-call votes for a representative, optionally filtered by date."""
        return self._repo.get_votes_for_rep(rep_id, from_date, to_date)

    def get_votes_by_industry(
        self,
        rep_id: RepId,
        industry: Industry,
        from_date: datetime | None = None,
    ) -> list[RollCallVote]:
        """
        Return votes where the bill is tagged with the given industry.

        Used by the CorrelationEngine (Sprint 8) to compute before/after
        alignment scores following a major donation event.
        """
        all_votes = self._repo.get_votes_for_rep(rep_id, from_date)
        # Bills fetched via raw_votes don't carry industry tags inline;
        # the caller is expected to enrich results using get_bill() if needed.
        # This method is a hook for Sprint 8 — it returns unfiltered for now.
        return all_votes
