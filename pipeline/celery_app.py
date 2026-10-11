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

from celery import Celery, chain, chord, group
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
    # si() = immutable signature: prevents the previous task's return value
    # from being forwarded as an argument to the next task.
    def si(name: str):
        return celery_app.signature(name, immutable=True)

    # Stage 1: ingest_fec and ingest_votes in parallel
    # Stage 2: resolve_identities and classify_bills in parallel
    #          (resolve → aggregate_finance as a chain; classify_bills standalone)
    # Stage 3: compute_correlations waits for both aggregate_finance and classify_bills
    chord(
        group(
            si("pipeline.tasks.ingest_fec.run"),
            si("pipeline.tasks.ingest_votes.run"),
        ),
        chord(
            group(
                chain(
                    si("pipeline.tasks.resolve_identities.run"),
                    si("pipeline.tasks.aggregate_finance.run"),
                ),
                si("pipeline.tasks.classify_bills.run"),
            ),
            si("pipeline.tasks.compute_correlations.run"),
        ),
    ).delay()
