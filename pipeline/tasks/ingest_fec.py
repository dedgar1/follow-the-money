"""Stage 1a: Ingest FEC contribution data into raw tables."""

from __future__ import annotations

from pipeline.celery_app import celery_app


@celery_app.task(name="pipeline.tasks.ingest_fec.run", bind=True, max_retries=3)
def run(self):
    """TODO Sprint 2: Fetch FEC API → raw contributions table."""
    raise NotImplementedError("TODO Sprint 2")
