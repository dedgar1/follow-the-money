"""Neo4j connection — re-exports the shared driver from infrastructure."""

from infrastructure.neo4j_driver import check_neo4j_health, close_driver, get_driver

__all__ = ["get_driver", "close_driver", "check_neo4j_health"]
