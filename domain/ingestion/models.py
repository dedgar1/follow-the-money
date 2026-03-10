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
    Raw roll-call vote record. One row per (member, roll_call).

    Sources:
      House  → Congress.gov API v3  (source="congress_api")
      Senate → Senate.gov XML feeds (source="senate_xml")
    """

    id: str                              # internal ULID
    source: str = "congress_api"
    source_id: str = ""                  # unique vote URI / identifier (idempotency key)
    congress: int = 0
    session: int = 1
    chamber: str = ""                    # "House" | "Senate"
    roll_call: int = 0
    bill_id: str = ""                    # e.g. "3424" (HR) or "PN373" (Senate nomination)
    bill_title: str = ""
    member_bioguide_id: str = ""         # bioguide_id (House) or lis_member_id (Senate, resolved in Sprint 3)
    member_name: str = ""
    position: str = ""                   # "Yea" | "Nay" | "Not Voting" | "Present"
    voted_at: str = ""                   # "YYYY-MM-DD" raw string
    payload: dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=_now)
    is_processed: bool = False
