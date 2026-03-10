"""Stage 1b: Ingest ProPublica vote data into raw tables."""

from __future__ import annotations

from pipeline.celery_app import celery_app


@celery_app.task(name="pipeline.tasks.ingest_votes.run", bind=True, max_retries=3)
def run(self):
    """TODO Sprint 2: Fetch ProPublica API → raw votes + bills tables."""
    raise NotImplementedError("TODO Sprint 2")
