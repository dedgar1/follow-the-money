"""Stage 3: Aggregate contributions → DonorRepRelationships + Neo4j graph."""

from __future__ import annotations

from pipeline.celery_app import celery_app


@celery_app.task(name="pipeline.tasks.aggregate_finance.run", bind=True, max_retries=3)
def run(self):
    """TODO Sprint 4: Aggregate contributions → PostgreSQL materialized views + Neo4j."""
    raise NotImplementedError("TODO Sprint 4")
