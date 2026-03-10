"""
Ingestion bounded context — raw data exactly as received from external APIs.

Raw records are IMMUTABLE after insert. They are never updated.
All downstream contexts (Identity, Finance, Voting) read from these tables
and write to their own canonical tables.

TODO Sprint 2: Implement RawFiling, RawVote, RawDonor fully.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RawFiling:
    """Raw individual contribution or PAC filing from FEC Schedule A."""

    id: str                              # internal ULID assigned at ingest time
    source: str = "fec_api"
    source_id: str = ""                  # FEC transaction_id
    payload: dict[str, Any] = field(default_factory=dict)  # verbatim API JSON
    fetched_at: datetime = field(default_factory=_now)
    is_processed: bool = False           # True after identity resolution (Sprint 3)


@dataclass
class RawDonor:
    """Raw donor/committee record from FEC API."""

    id: str                              # internal ULID
    source: str = "fec_api"
    source_id: str = ""                  # FEC committee_id
    payload: dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=_now)
    is_processed: bool = False


@dataclass
class RawVote:
    """Raw roll-call vote record from ProPublica Congress API."""

    id: str                              # internal ULID
    source: str = "propublica_api"
    source_id: str = ""                  # ProPublica roll call URI
    payload: dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=_now)
    is_processed: bool = False
