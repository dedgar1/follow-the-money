"""Stage 2a: Resolve raw donor/rep names to canonical entities."""

from __future__ import annotations

from pipeline.celery_app import celery_app


@celery_app.task(name="pipeline.tasks.resolve_identities.run", bind=True, max_retries=3)
def run(self):
    """TODO Sprint 3: rapidfuzz deduplication → canonical entities."""
    raise NotImplementedError("TODO Sprint 3")
