"""
Voting record service.

TODO Sprint 7: Implement VotingRecordService with ProPublica data + NLP tagging.
"""

from __future__ import annotations

from domain.voting.ports import VotingRepository


class VotingRecordService:
    def __init__(self, repo: VotingRepository) -> None:
        self._repo = repo

    # TODO Sprint 7: get_record_for_rep, get_votes_by_industry
