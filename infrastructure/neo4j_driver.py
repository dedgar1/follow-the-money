"""
Neo4j driver — singleton GraphDatabase driver and health check.

All adapters call get_driver() to obtain the shared driver instance.
Call close_driver() on application shutdown (wired into FastAPI lifespan).
"""

from __future__ import annotations

from neo4j import Driver, GraphDatabase

from infrastructure.config import get_settings

_driver: Driver | None = None


def get_driver() -> Driver:
    global _driver
    if _driver is None:
        settings = get_settings()
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def check_neo4j_health() -> bool:
    """Returns True if Neo4j is reachable via Bolt."""
    try:
        driver = get_driver()
        driver.verify_connectivity()
        return True
    except Exception:
        return False
