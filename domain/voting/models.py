"""
Voting bounded context — bills, roll call votes, and sponsorships.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import NewType

from domain.identity.models import CanonicalRepRef
from domain.shared.industry import Industry

BillId = NewType("BillId", str)
VoteId = NewType("VoteId", str)


class VotePosition(str, Enum):
    YES        = "yes"
    NO         = "no"
    ABSTAIN    = "abstain"
    NOT_VOTING = "not_voting"


class VoteType(str, Enum):
    FLOOR     = "floor"
    COMMITTEE = "committee"


class SponsorRole(str, Enum):
    SPONSOR    = "sponsor"
    COSPONSOR  = "cosponsor"


@dataclass(frozen=True)
class BillRef:
    id:    BillId
    title: str


@dataclass
class Bill:
    id:              BillId
    title:           str
    industries:      list[Industry] = field(default_factory=list)  # NLP-assigned
    nlp_confidence:  float = 0.0
    congress:        int | None = None     # e.g. 118
    propublica_id:   str | None = None    # ProPublica bill slug


@dataclass
class RollCallVote:
    id:             VoteId
    bill:           BillRef
    representative: CanonicalRepRef
    position:       VotePosition
    voted_at:       datetime
    vote_type:      VoteType = VoteType.FLOOR


@dataclass
class Sponsorship:
    bill:           BillRef
    representative: CanonicalRepRef
    role:           SponsorRole
