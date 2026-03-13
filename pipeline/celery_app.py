"""
Celery application — broker and result backend use Redis.

Nightly pipeline runs at 02:00 UTC via beat schedule.
Failure mode: FAIL LOUD — any stage failure halts downstream stages.

The beat schedule only triggers the first task (ingest_fec). That task
launches the full pipeline as a Celery chain so each stage only runs if
the previous one completed successfully.

Pipeline order:
  ingest_fec → ingest_votes → resolve_identities → classify_bills
             → aggregate_finance → compute_correlations
"""

from __future__ import annotations

from celery import Celery, chain, group
from celery.schedules import crontab

from infrastructure.config import get_settings


def make_celery() -> Celery:
    settings = get_settings()
    app = Celery(
        "follow_the_money",
        broker=settings.redis_url,
        backend=settings.redis_url,
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
    )
    app.conf.beat_schedule = {
        "nightly-pipeline": {
            "task": "pipeline.celery_app.run_pipeline",
            "schedule": crontab(hour=2, minute=0),
        },
    }
    # Explicitly include each task module (autodiscover_tasks requires a tasks.py
    # convention; our tasks live in individual files within pipeline/tasks/).
    app.conf.include = [
        "pipeline.celery_app",
        "pipeline.tasks.ingest_fec",
        "pipeline.tasks.ingest_votes",
        "pipeline.tasks.resolve_identities",
        "pipeline.tasks.aggregate_finance",
        "pipeline.tasks.classify_bills",
        "pipeline.tasks.compute_correlations",
    ]
    return app


celery_app = make_celery()


@celery_app.task(name="pipeline.celery_app.run_pipeline")
def run_pipeline() -> None:
    """
    Launch the full nightly pipeline as a chain.
    Each stage only executes if the previous one succeeded.
    """
    tail = [
        celery_app.signature("pipeline.tasks.resolve_identities.run"),
        celery_app.signature("pipeline.tasks.classify_bills.run"),
        celery_app.signature("pipeline.tasks.aggregate_finance.run"),
        celery_app.signature("pipeline.tasks.compute_correlations.run"),
    ]
    group(
        chain(celery_app.signature("pipeline.tasks.ingest_fec.run"), *tail),
        chain(celery_app.signature("pipeline.tasks.ingest_votes.run"), *tail),
    ).delay()
