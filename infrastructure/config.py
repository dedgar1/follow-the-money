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
    propublica_api_key: str = Field(default="")
    opensecrets_api_key: str = Field(default="")
    google_civic_api_key: str = Field(default="")

    # ── Methodology URL ───────────────────────────────────────────────────
    methodology_url: str = Field(default="http://localhost:3000/methodology")


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — call this everywhere instead of instantiating Settings()."""
    return Settings()
