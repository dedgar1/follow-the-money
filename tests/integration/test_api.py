"""
Integration tests for REST endpoints and GraphQL.

All REST v1 endpoints return 501 until their sprint is implemented.
GraphQL hello query returns the expected version string.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)

# ── REST — 501 smoke tests ────────────────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "/v1/representatives",
    "/v1/representatives/rep1",
    "/v1/representatives/rep1/votes",
    "/v1/representatives/rep1/correlations",
    "/v1/donors/donor1",
    "/v1/donors/donor1/recipients",
    "/v1/search?q=smith",
    "/v1/zip/90210",
    "/v1/compare?ids=rep1,rep2",
    "/v1/export/rep1.csv",
])
def test_unimplemented_rest_endpoints_return_501(path: str):
    response = client.get(path)
    assert response.status_code == 501
    assert "detail" in response.json()


# ── GraphQL ───────────────────────────────────────────────────────────────────

def test_graphql_hello_query():
    response = client.post("/graphql", json={"query": "{ hello }"})
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["hello"] == "Follow the Money GraphQL API — v0.1.0"


def test_graphql_introspection():
    response = client.post("/graphql", json={"query": "{ __typename }"})
    assert response.status_code == 200


# ── Health with Redis (Sprint 2 addition) ─────────────────────────────────────

def test_health_includes_version():
    with (
        patch("infrastructure.database.check_postgres_health", return_value=True),
        patch("infrastructure.neo4j_driver.check_neo4j_health", return_value=True),
    ):
        data = client.get("/health").json()
    assert data["version"] == "0.1.0"


def test_health_ok_when_all_services_up():
    with (
        patch("infrastructure.database.check_postgres_health", return_value=True),
        patch("infrastructure.neo4j_driver.check_neo4j_health", return_value=True),
    ):
        data = client.get("/health").json()
    assert data["status"] == "ok"


def test_health_degraded_when_neo4j_down():
    with (
        patch("infrastructure.database.check_postgres_health", return_value=True),
        patch("infrastructure.neo4j_driver.check_neo4j_health", return_value=False),
    ):
        data = client.get("/health").json()
    assert data["status"] == "degraded"
    assert data["neo4j"] is False
