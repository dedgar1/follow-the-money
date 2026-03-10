"""
Ingestion service — coordinates raw data fetching and storage.

TODO Sprint 2: Implement IngestionService using FEC and Congress.gov adapters.
"""

from __future__ import annotations

from domain.ingestion.ports import RawIngestionRepository


class IngestionService:
    """Orchestrates raw data ingestion from external APIs into raw tables."""

    def __init__(self, repo: RawIngestionRepository) -> None:
        self._repo = repo

    # TODO Sprint 2: ingest_fec_contributions, ingest_congress_votes
