"""
Celery application — broker and result backend use Redis.

Nightly pipeline runs at 02:00 UTC via beat schedule.
Failure mode: FAIL LOUD — any stage failure halts downstream stages.
"""

from __future__ import annotations

from celery import Celery
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
        "nightly-ingest-fec": {
            "task": "pipeline.tasks.ingest_fec.run",
            "schedule": crontab(hour=2, minute=0),
        },
        "nightly-ingest-votes": {
            "task": "pipeline.tasks.ingest_votes.run",
            "schedule": crontab(hour=2, minute=15),  # 15 min after FEC ingest starts
        },
        "nightly-resolve-identities": {
            "task": "pipeline.tasks.resolve_identities.run",
            "schedule": crontab(hour=4, minute=0),   # after both ingest tasks complete
        },
        "nightly-aggregate-finance": {
            "task": "pipeline.tasks.aggregate_finance.run",
            "schedule": crontab(hour=6, minute=0),   # after identity resolution completes
        },
    }
    # Explicitly include each task module (autodiscover_tasks requires a tasks.py
    # convention; our tasks live in individual files within pipeline/tasks/).
    app.conf.include = [
        "pipeline.tasks.ingest_fec",
        "pipeline.tasks.ingest_votes",
        "pipeline.tasks.resolve_identities",
        "pipeline.tasks.aggregate_finance",
        "pipeline.tasks.classify_bills",
        "pipeline.tasks.compute_correlations",
    ]
    return app


celery_app = make_celery()
