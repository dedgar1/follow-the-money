"""Stage 2b: Tag bills with Industry categories via spaCy NLP."""

from __future__ import annotations

from pipeline.celery_app import celery_app


@celery_app.task(name="pipeline.tasks.classify_bills.run", bind=True, max_retries=3)
def run(self):
    """TODO Sprint 7: spaCy NLP → industry tags on bills."""
    raise NotImplementedError("TODO Sprint 7")
