"""
Statistical functions for correlation analysis.

TODO Sprint 8: Implement Fisher's exact test, shift detection, confidence scoring.
"""

from __future__ import annotations


def fishers_exact_test(
    before_yes: int,
    before_no: int,
    after_yes: int,
    after_no: int,
) -> float:
    """
    Returns p-value from Fisher's exact test comparing voting alignment
    before and after a major donation event.

    TODO Sprint 8: Implement using scipy.stats.fisher_exact.
    """
    raise NotImplementedError("TODO Sprint 8")


def compute_alignment_score(yes_votes: int, total_votes: int) -> float:
    """
    Returns alignment score in [0.0, 1.0] where 1.0 = always voted yes.

    TODO Sprint 8: Implement with weighting by vote type and recency.
    """
    raise NotImplementedError("TODO Sprint 8")
