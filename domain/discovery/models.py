"""
Discovery bounded context — search index and ZIP-to-district lookup.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.identity.models import CanonicalRepRef


@dataclass
class SearchResult:
    id:          str
    label:       str          # Display name
    result_type: str          # "rep" | "donor"
    ref:         CanonicalRepRef | None = None


@dataclass
class DistrictMap:
    zip_code:  str
    state:     str
    district:  str
    reps:      list[CanonicalRepRef] = field(default_factory=list)
