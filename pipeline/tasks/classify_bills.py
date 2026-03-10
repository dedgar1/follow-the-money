"""
Stage 2b: Tag bills with Industry categories via BillClassifier — Sprint 7.

Reads all untagged (or low-confidence) bills from the bills table,
classifies each via keyword taxonomy, and writes back industries + confidence.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import text

from adapters.nlp.bill_classifier import BillClassifier
from infrastructure.database import get_session
from pipeline.celery_app import celery_app
from pipeline.monitoring.alerting import send_pipeline_failure_alert, send_pipeline_success_alert

logger = logging.getLogger(__name__)

_MIN_CONFIDENCE_THRESHOLD = 0.1  # re-classify bills below this confidence


@celery_app.task(
    name="pipeline.tasks.classify_bills.run",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run(self) -> dict:
    """
    Classify all bills in the bills table that are untagged or have
    low NLP confidence.  Updates industries + nlp_confidence in-place.

    Returns {"bills_classified": N}.
    """
    logger.info("classify_bills: starting")
    try:
        count = _classify_all_bills()
    except Exception as exc:
        logger.exception("classify_bills: error: %s", exc)
        try:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            send_pipeline_failure_alert("classify_bills", exc)
            raise

    send_pipeline_success_alert("classify_bills", rows_written=count)
    logger.info("classify_bills: done — %d bills classified", count)
    return {"bills_classified": count}


def _classify_all_bills() -> int:
    """Core classification logic — testable without Celery."""
    classifier = BillClassifier()

    with get_session() as db:
        rows = db.execute(
            text(
                "SELECT id, title, industries, nlp_confidence "
                "FROM bills "
                "WHERE nlp_confidence < :threshold OR industries = '[]' OR industries IS NULL "
                "ORDER BY id"
            ),
            {"threshold": _MIN_CONFIDENCE_THRESHOLD},
        ).fetchall()

        classified = 0
        for row in rows:
            bill_id, title, industries_json, _ = row
            # If bill already has subjects stored in payload, we could load them here.
            # For now, classify from title only.
            industry, confidence = classifier.classify(title)
            new_industries = json.dumps([industry.value])

            db.execute(
                text(
                    "UPDATE bills SET industries = :industries, nlp_confidence = :conf "
                    "WHERE id = :id"
                ),
                {"industries": new_industries, "conf": confidence, "id": bill_id},
            )
            classified += 1

        db.commit()

    return classified
