"""
Identity bounded context — canonical, resolved entities.

CanonicalRep and CanonicalDonor are deduplicated representations of
real-world people and organizations, produced by the identity resolution
pipeline (Sprint 3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, NewType

if TYPE_CHECKING:
    from domain.shared.industry import Industry

RepId   = NewType("RepId", str)
DonorId = NewType("DonorId", str)


class Chamber(str, Enum):
    HOUSE  = "house"
    SENATE = "senate"


class Party(str, Enum):
    DEMOCRAT    = "D"
    REPUBLICAN  = "R"
    INDEPENDENT = "I"
    OTHER       = "O"


class DonorType(str, Enum):
    INDIVIDUAL  = "individual"
    PAC         = "pac"
    CORPORATION = "corporation"
    UNION       = "union"
    OTHER       = "other"


@dataclass
class CanonicalRep:
    id:                RepId
    full_name:         str
    party:             Party
    chamber:           Chamber
    state:             str           # 2-letter state code
    district:          str | None    # e.g. "CA-12" (None for Senate)
    bioguide_id:       str | None    # Congress.gov identifier
    fec_candidate_id:  str | None    # FEC identifier

    def __post_init__(self) -> None:
        if len(self.state) != 2:
            raise ValueError(f"State must be a 2-letter code, got '{self.state}'")
        if not self.full_name.strip():
            raise ValueError("Representative name cannot be empty")


@dataclass
class CanonicalDonor:
    id:         DonorId
    name:       str            # Resolved canonical name (post-deduplication)
    donor_type: DonorType
    industry:   Industry | None
    state:      str | None     # Donor home state
    fec_ids:    list[str] = field(default_factory=list)  # All FEC IDs mapped here

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Donor name cannot be empty")


# Lightweight cross-context reference types
@dataclass(frozen=True)
class CanonicalRepRef:
    id:        RepId
    full_name: str


@dataclass(frozen=True)
class CanonicalDonorRef:
    id:   DonorId
    name: str
