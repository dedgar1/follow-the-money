"""
Correlation bounded context — alignment scores and correlation events.

Statistical rules (from CLAUDE.md):
  - evidence_count >= 5
  - |shift| >= 0.15
  - p-value < 0.05 (Fisher's exact test)
  - Before/after window: 24 months each side of the major donation event
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import NewType

from domain.identity.models import CanonicalDonorRef, CanonicalRepRef
from domain.shared.industry import Industry
from domain.shared.money import Money

AlignmentScoreId   = NewType("AlignmentScoreId", str)
CorrelationEventId = NewType("CorrelationEventId", str)


class ConfidenceLevel(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


@dataclass
class AlignmentScore:
    id:               AlignmentScoreId
    representative:   CanonicalRepRef
    donor:            CanonicalDonorRef
    industry:         Industry
    score:            float           # 0.0 – 1.0 overall alignment
    confidence:       ConfidenceLevel
    evidence_count:   int             # number of relevant votes in window
    before_score:     float           # alignment BEFORE major donation
    after_score:      float           # alignment AFTER major donation
    shift:            float           # after_score - before_score (THE key signal)
    p_value:          float           # Fisher's exact test result
    methodology_url:  str             # always link to the public methodology page
    computed_at:      date | None = None

    def is_significant(self) -> bool:
        """Returns True if this score meets all statistical thresholds."""
        return (
            self.evidence_count >= 5
            and abs(self.shift) >= 0.15
            and self.p_value < 0.05
        )


@dataclass
class CorrelationEvent:
    """A significant donation event that triggers before/after analysis."""

    id:               CorrelationEventId
    representative:   CanonicalRepRef
    donor:            CanonicalDonorRef
    industry:         Industry
    event_date:       date
    threshold_amount: Money    # the donation amount that triggered this event
