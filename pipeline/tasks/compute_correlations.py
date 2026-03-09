"""Stage 4: Compute AlignmentScore for each (rep, industry) pair."""

from __future__ import annotations

from pipeline.celery_app import celery_app


@celery_app.task(name="pipeline.tasks.compute_correlations.run", bind=True, max_retries=3)
def run(self):
    """TODO Sprint 8: CorrelationEngine → AlignmentScore per (rep, industry)."""
    raise NotImplementedError("TODO Sprint 8")
