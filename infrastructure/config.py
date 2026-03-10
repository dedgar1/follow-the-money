"""
Application configuration — all settings loaded from environment variables.

Copy .env.example to .env and fill in your values before running locally.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──────────────────────────────────────────────────────────────
    app_name: str = "FollowTheMoney"
    debug: bool = False
    log_level: str = "INFO"

    # ── PostgreSQL ───────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql://ftm:ftm@localhost:5432/follow_the_money",
    )

    # ── Redis / Celery ───────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ── Neo4j ────────────────────────────────────────────────────────────
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="ftm_dev_password")

    # ── External APIs (Sprint 2) ──────────────────────────────────────────
    fec_api_key: str = Field(default="")
    congress_api_key: str = Field(default="")   # api.congress.gov — replaces ProPublica
    opensecrets_api_key: str = Field(default="")
    google_civic_api_key: str = Field(default="")

    # ── Alerting (Sprint 2) ───────────────────────────────────────────────────
    slack_webhook_url: str = Field(default="")
    alert_email_to: str = Field(default="")
    alert_email_from: str = Field(default="alerts@followthemoney.local")
    smtp_host: str = Field(default="localhost")
    smtp_port: int = Field(default=587)

    # ── Congress metadata ─────────────────────────────────────────────────────
    current_congress: int = Field(default=119)   # update each new Congress
    current_session: int = Field(default=1)

    # ── Methodology URL ───────────────────────────────────────────────────
    methodology_url: str = Field(default="http://localhost:3000/methodology")


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — call this everywhere instead of instantiating Settings()."""
    return Settings()
