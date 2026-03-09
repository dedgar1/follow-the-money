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
    }
    # Auto-discover tasks in pipeline.tasks.*
    app.autodiscover_tasks(["pipeline.tasks"])
    return app


celery_app = make_celery()
