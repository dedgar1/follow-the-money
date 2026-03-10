"""Pipeline health check — verifies all external services are reachable."""

from __future__ import annotations

from infrastructure.database import check_postgres_health
from infrastructure.neo4j_driver import check_neo4j_health
from infrastructure.redis_client import check_redis_health


def check_all() -> dict[str, bool]:
    return {
        "postgres": check_postgres_health(),
        "neo4j": check_neo4j_health(),
        "redis": check_redis_health(),
    }
