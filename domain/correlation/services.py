"""
Correlation engine — computes AlignmentScore for each (rep, industry) pair.

The engine is a pure domain service: it accepts pre-loaded data from the
calling task/adapter and returns domain objects.  No framework imports.

Algorithm (per CLAUDE.md):
  - evidence_count >= 5 (relevant votes in window)
  - |shift| >= 0.15 (15-point alignment change)
  - p-value < 0.05 (Fisher's exact test)
  - Before/after window = 24 months each side of the major donation event

A vote is "industry-aligned" if position == YES on a bill tagged with the
industry.  NO / ABSTAIN / NOT_VOTING count as non-aligned.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from ulid import ULID

from domain.correlation.models import (
    AlignmentScore,
    AlignmentScoreId,
    ConfidenceLevel,
    CorrelationEvent,
    CorrelationEventId,
)
from domain.correlation.ports import CorrelationRepository
from domain.correlation.statistics import compute_alignment_score, fishers_exact_test
from domain.finance.models import DonorRepRelationship
from domain.finance.ports import FinanceRepository
from domain.identity.models import CanonicalRepRef
from domain.shared.industry import Industry
from domain.shared.money import Money
from domain.voting.models import RollCallVote, VotePosition
from domain.voting.ports import VotingRepository

if TYPE_CHECKING:
    pass

# 24 months expressed in days (730 ≈ 2 years)
_WINDOW_DAYS = 730

_METHODOLOGY_URL = "/docs/methodology"


class CorrelationEngine:
    def __init__(
        self,
        finance_repo: FinanceRepository,
        voting_repo: VotingRepository,
        correlation_repo: CorrelationRepository,
    ) -> None:
        self._finance = finance_repo
        self._voting = voting_repo
        self._correlation = correlation_repo

    # ── Public API ────────────────────────────────────────────────────────────

    def compute_for_rep(
        self,
        rep_ref: CanonicalRepRef,
        industry_relationships: list[tuple[DonorRepRelationship, Industry | None]],
        tagged_votes: list[tuple[RollCallVote, list[Industry]]],
        methodology_url: str = _METHODOLOGY_URL,
    ) -> list[AlignmentScore]:
        """
        Compute AlignmentScores for one representative.

        Parameters
        ----------
        rep_ref:
            Canonical ref for the rep being analysed.
        industry_relationships:
            Each (DonorRepRelationship, industry) pair where industry is the
            canonical_donors.industry value (may be None if unclassified).
        tagged_votes:
            Each (RollCallVote, industries) pair where industries is the list
            of Industry values NLP-assigned to the bill the vote is about.
        methodology_url:
            Link to methodology page — embedded in every AlignmentScore.

        Returns
        -------
        list[AlignmentScore]
            Only scores that meet ALL three significance thresholds are returned.
        """
        # Group relationships by industry
        industry_groups: dict[Industry, list[DonorRepRelationship]] = {}
        for rel, industry in industry_relationships:
            if industry is None:
                continue
            industry_groups.setdefault(industry, []).append(rel)

        scores: list[AlignmentScore] = []

        for industry, rels in industry_groups.items():
            score = _compute_industry_score(
                rep_ref=rep_ref,
                industry=industry,
                rels=rels,
                tagged_votes=tagged_votes,
                methodology_url=methodology_url,
            )
            if score is not None and score.is_significant():
                scores.append(score)

        return scores


# ── Internal helpers ───────────────────────────────────────────────────────────


def _compute_industry_score(
    rep_ref: CanonicalRepRef,
    industry: Industry,
    rels: list[DonorRepRelationship],
    tagged_votes: list[tuple[RollCallVote, list[Industry]]],
    methodology_url: str,
) -> AlignmentScore | None:
    """
    Compute a single AlignmentScore for one (rep, industry) pair.
    Returns None when there isn't enough data to produce a meaningful score.
    """
    # Major event date = latest donation received from this industry
    event_date = _find_event_date(rels)
    if event_date is None:
        return None

    window_start = event_date - timedelta(days=_WINDOW_DAYS)
    window_end = event_date + timedelta(days=_WINDOW_DAYS)

    # Filter to votes on bills tagged with this industry
    industry_votes = [
        vote
        for vote, industries in tagged_votes
        if industry in industries
    ]

    # Split into before / after windows
    before_votes = [
        v for v in industry_votes
        if window_start <= v.voted_at.date() < event_date
    ]
    after_votes = [
        v for v in industry_votes
        if event_date <= v.voted_at.date() <= window_end
    ]

    evidence_count = len(before_votes) + len(after_votes)
    if evidence_count < 5:
        return None

    # Count aligned (YES) vs non-aligned votes in each window
    before_yes = sum(1 for v in before_votes if v.position == VotePosition.YES)
    before_no = len(before_votes) - before_yes
    after_yes = sum(1 for v in after_votes if v.position == VotePosition.YES)
    after_no = len(after_votes) - after_yes

    before_score = compute_alignment_score(before_yes, len(before_votes))
    after_score = compute_alignment_score(after_yes, len(after_votes))
    shift = after_score - before_score

    overall_total = len(before_votes) + len(after_votes)
    overall_score = compute_alignment_score(before_yes + after_yes, overall_total)

    p_value = fishers_exact_test(before_yes, before_no, after_yes, after_no)

    confidence = _confidence(p_value, evidence_count)

    # Primary donor = largest total amount in this industry group
    primary_rel = max(rels, key=lambda r: r.total_amount.cents)

    return AlignmentScore(
        id=AlignmentScoreId(str(ULID())),
        representative=rep_ref,
        donor=primary_rel.donor,
        industry=industry,
        score=round(overall_score, 4),
        confidence=confidence,
        evidence_count=evidence_count,
        before_score=round(before_score, 4),
        after_score=round(after_score, 4),
        shift=round(shift, 4),
        p_value=round(p_value, 6),
        methodology_url=methodology_url,
        computed_at=date.today(),
    )


def _find_event_date(rels: list[DonorRepRelationship]) -> date | None:
    """
    Major event date = the latest donation date across all relationships
    in the industry group.  This is the point that divides before/after.
    """
    latest: date | None = None
    for rel in rels:
        if rel.latest_donation is not None:
            if latest is None or rel.latest_donation > latest:
                latest = rel.latest_donation
    return latest


def _confidence(p_value: float, evidence_count: int) -> ConfidenceLevel:
    if p_value < 0.01 and evidence_count >= 20:
        return ConfidenceLevel.HIGH
    if p_value < 0.05 and evidence_count >= 10:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW
