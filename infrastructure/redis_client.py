"""
Redis client — singleton factory and health check.

Follows the same pattern as database.py and neo4j_driver.py.
"""

from __future__ import annotations

import redis

from infrastructure.config import get_settings


def get_redis_client() -> redis.Redis:
    """Return a Redis client connected to the configured URL."""
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)


def check_redis_health() -> bool:
    """Returns True if Redis is reachable."""
    try:
        get_redis_client().ping()
        return True
    except Exception:
        return False
