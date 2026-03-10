"""
Ingestion context output ports — abstract interfaces for raw data persistence.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.ingestion.models import RawDonor, RawFiling, RawVote


class RawIngestionRepository(ABC):
    @abstractmethod
    def save_filing(self, filing: RawFiling) -> None: ...

    @abstractmethod
    def save_filings(self, filings: list[RawFiling]) -> None: ...

    @abstractmethod
    def save_donor(self, donor: RawDonor) -> None: ...

    @abstractmethod
    def save_vote(self, vote: RawVote) -> None: ...

    @abstractmethod
    def save_votes(self, votes: list[RawVote]) -> None: ...

    @abstractmethod
    def get_unprocessed_filings(self, limit: int = 1000) -> list[RawFiling]: ...

    @abstractmethod
    def get_unprocessed_votes(self, limit: int = 1000) -> list[RawVote]: ...

    @abstractmethod
    def mark_filing_processed(self, filing_id: str) -> None: ...

    @abstractmethod
    def mark_vote_processed(self, vote_id: str) -> None: ...
