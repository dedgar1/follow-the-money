"""
Finance bounded context — contributions and the aggregate root.

Per CLAUDE.md: "The primary domain object is the Relationship between
a donor and a representative — not the transaction, not the representative,
not the donor."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import NewType

from domain.identity.models import CanonicalDonorRef, CanonicalRepRef
from domain.shared.election_cycle import ElectionCycle
from domain.shared.money import Money

RelationshipId = NewType("RelationshipId", str)
ContributionId = NewType("ContributionId", str)


from enum import Enum


class ContributionType(str, Enum):
    INDIVIDUAL  = "individual"
    PAC         = "pac"
    SUPER_PAC   = "super_pac"
    DARK_MONEY  = "dark_money"


@dataclass
class Contribution:
    id:                ContributionId
    donor_id:          str
    representative_id: str
    amount:            Money
    contributed_on:    date
    election_cycle:    ElectionCycle
    contribution_type: str
    fec_filing_id:     str | None = None


@dataclass
class DonorRepRelationship:
    """
    THE AGGREGATE ROOT.

    Encapsulates the entire financial relationship between one donor and one
    representative across all election cycles.
    """

    id:              RelationshipId
    donor:           CanonicalDonorRef
    representative:  CanonicalRepRef
    contributions:   list[Contribution] = field(default_factory=list)
    first_donation:  date | None = None
    latest_donation: date | None = None
    total_amount:    Money = field(default_factory=lambda: Money(cents=0))
    cycles:          list[ElectionCycle] = field(default_factory=list)

    def add_contribution(self, c: Contribution) -> None:
        self.contributions.append(c)
        self.total_amount = self.total_amount + c.amount

        if self.first_donation is None or c.contributed_on < self.first_donation:
            self.first_donation = c.contributed_on
        if self.latest_donation is None or c.contributed_on > self.latest_donation:
            self.latest_donation = c.contributed_on

        if c.election_cycle not in self.cycles:
            self.cycles.append(c.election_cycle)
