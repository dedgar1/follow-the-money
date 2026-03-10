"""
Fail-loud alerting — Slack webhook + email on pipeline failure.

Architecture rule: FAIL LOUD.
- Any stage failure → immediate alert (Slack + email if configured).
- Pipeline halts — downstream stages do not run on partial data.
- This module is the single place all alerts go through.
"""

from __future__ import annotations

import json
import logging
import smtplib
from email.mime.text import MIMEText

import httpx

from infrastructure.config import get_settings

logger = logging.getLogger(__name__)


def send_pipeline_failure_alert(
    stage: str,
    error: Exception,
    *,
    extra: dict | None = None,
) -> None:
    """
    Send a failure alert via all configured channels (Slack and/or email).

    This is called by pipeline tasks on unrecoverable failures (after retries
    are exhausted). Logs the error regardless of whether external channels succeed.

    Args:
        stage: Human-readable pipeline stage name, e.g. "ingest_fec".
        error: The exception that caused the failure.
        extra: Optional dict of additional context to include in the alert.
    """
    message = _format_message(stage, error, extra)
    logger.error("PIPELINE FAILURE [%s]: %s", stage, error)

    settings = get_settings()

    if settings.slack_webhook_url:
        _send_slack(settings.slack_webhook_url, message, stage)

    if settings.alert_email_to:
        _send_email(
            to=settings.alert_email_to,
            from_addr=settings.alert_email_from,
            subject=f"[Follow the Money] Pipeline failure: {stage}",
            body=message,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
        )


def send_pipeline_success_alert(stage: str, *, rows_written: int = 0) -> None:
    """
    Log (and optionally Slack) a successful pipeline stage completion.

    Success alerts are low-priority — Slack is only used if a webhook is configured
    and the message is deliberately brief to avoid noise.
    """
    message = f":white_check_mark: Pipeline stage `{stage}` completed — {rows_written} rows written."
    logger.info("PIPELINE SUCCESS [%s]: %d rows written", stage, rows_written)

    settings = get_settings()
    if settings.slack_webhook_url:
        _send_slack(settings.slack_webhook_url, message, stage, is_failure=False)


# ── Internal helpers ──────────────────────────────────────────────────────────


def _format_message(stage: str, error: Exception, extra: dict | None) -> str:
    lines = [
        f"Pipeline stage FAILED: {stage}",
        f"Error: {type(error).__name__}: {error}",
    ]
    if extra:
        for key, value in extra.items():
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def _send_slack(webhook_url: str, message: str, stage: str, *, is_failure: bool = True) -> None:
    color = "#E63022" if is_failure else "#36a64f"
    payload = {
        "attachments": [
            {
                "color": color,
                "title": f"Follow the Money — pipeline {'failure' if is_failure else 'success'}: {stage}",
                "text": message,
                "footer": "Follow the Money pipeline",
            }
        ]
    }
    try:
        response = httpx.post(webhook_url, json=payload, timeout=10.0)
        response.raise_for_status()
    except Exception as exc:
        # Never let alerting failure crash the caller — just log it.
        logger.warning("Failed to send Slack alert: %s", exc)


def _send_email(
    *,
    to: str,
    from_addr: str,
    subject: str,
    body: str,
    smtp_host: str,
    smtp_port: int,
) -> None:
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
            smtp.sendmail(from_addr, [to], msg.as_string())
    except Exception as exc:
        logger.warning("Failed to send alert email: %s", exc)
