"""
Ingestion bounded context — raw data exactly as received from external APIs.

Raw records are IMMUTABLE after insert. They are never updated.
All downstream contexts (Identity, Finance, Voting) read from these tables
and write to their own canonical tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RawFiling:
    """
    Raw individual contribution or PAC filing from FEC Schedule A.
    One row per transaction exactly as returned by the FEC API.
    """

    id: str                              # internal ULID assigned at ingest time
    source: str = "fec_api"
    source_id: str = ""                  # FEC transaction_id (idempotency key)
    committee_id: str = ""               # FEC committee_id receiving the contribution
    contributor_name: str = ""
    contributor_employer: str = ""
    contributor_occupation: str = ""
    contributor_state: str = ""
    amount_cents: int = 0                # contribution_receipt_amount × 100
    contribution_date: str = ""          # "YYYY-MM-DD" raw string from API
    election_cycle: int = 0              # two_year_transaction_period
    payload: dict[str, Any] = field(default_factory=dict)   # verbatim API JSON
    fetched_at: datetime = field(default_factory=_now)
    is_processed: bool = False           # flipped after identity resolution (Sprint 3)


@dataclass
class RawDonor:
    """
    Raw donor/committee record from FEC API.
    Extracted from filings; deduplication into CanonicalDonor happens in Sprint 3.
    """

    id: str                              # internal ULID
    source: str = "fec_api"
    source_id: str = ""                  # FEC committee_id
    name: str = ""
    donor_type: str = ""                 # "individual" | "committee" | "pac"
    state: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=_now)
    is_processed: bool = False


@dataclass
class RawVote:
    """
    Raw roll-call vote from ProPublica Congress API.
    One row per (member, roll_call) — one vote per person per roll call.
    """

    id: str                              # internal ULID
    source: str = "propublica_api"
    source_id: str = ""                  # ProPublica roll_call_uri (idempotency key)
    congress: int = 0
    session: int = 1
    chamber: str = ""                    # "House" | "Senate"
    roll_call: int = 0
    bill_id: str = ""                    # ProPublica bill_id, e.g. "hr1-119"
    bill_title: str = ""
    member_bioguide_id: str = ""         # links to CanonicalRep via bioguide_id
    member_name: str = ""
    position: str = ""                   # "Yes" | "No" | "Not Voting" | "Present"
    voted_at: str = ""                   # "YYYY-MM-DD" raw string from API
    payload: dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=_now)
    is_processed: bool = False
