"""
Statistical functions for correlation analysis.

Uses scipy.stats.fisher_exact for the 2x2 contingency table test.
All functions are pure — no IO, no framework imports.
"""

from __future__ import annotations


def fishers_exact_test(
    before_yes: int,
    before_no: int,
    after_yes: int,
    after_no: int,
) -> float:
    """
    Returns two-tailed p-value from Fisher's exact test.

    Compares the proportion of industry-aligned votes (yes) before and
    after a major donation event.

    Contingency table:
        [before_yes, before_no]
        [after_yes,  after_no ]

    Returns 1.0 when any count is negative or the table is degenerate
    (all zeros in a row or column) — caller should treat as not significant.
    """
    from scipy.stats import fisher_exact  # type: ignore[import-untyped]

    if before_yes < 0 or before_no < 0 or after_yes < 0 or after_no < 0:
        return 1.0

    # Degenerate table — no information in at least one window
    if (before_yes + before_no) == 0 or (after_yes + after_no) == 0:
        return 1.0

    table = [[before_yes, before_no], [after_yes, after_no]]
    _, p_value = fisher_exact(table, alternative="two-sided")
    return float(p_value)


def compute_alignment_score(yes_votes: int, total_votes: int) -> float:
    """
    Returns alignment score in [0.0, 1.0] where 1.0 = 100% yes votes.

    A vote is "aligned" with an industry when the representative votes
    yes on a bill tagged to that industry.  NO / ABSTAIN / NOT_VOTING
    all count as non-aligned for this purpose.

    Returns 0.0 if total_votes is 0 (no information).
    """
    if total_votes <= 0:
        return 0.0
    yes_votes = max(0, min(yes_votes, total_votes))
    return yes_votes / total_votes
