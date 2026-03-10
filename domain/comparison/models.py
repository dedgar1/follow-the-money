"""
Comparison bounded context — side-by-side representative analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.finance.models import DonorRepRelationship
from domain.identity.models import CanonicalRepRef


@dataclass
class SharedDonor:
    donor_id:   str
    donor_name: str
    amounts:    dict[str, int]  # rep_id -> cents donated


@dataclass
class ComparisonReport:
    reps:          list[CanonicalRepRef]
    shared_donors: list[SharedDonor] = field(default_factory=list)
    relationships: list[DonorRepRelationship] = field(default_factory=list)
