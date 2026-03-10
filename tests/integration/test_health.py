"""Integration tests for the /health endpoint."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_health_returns_200():
    with (
        patch("infrastructure.database.check_postgres_health", return_value=True),
        patch("infrastructure.neo4j_driver.check_neo4j_health", return_value=True),
    ):
        response = client.get("/health")
    assert response.status_code == 200


def test_health_body_structure():
    with (
        patch("infrastructure.database.check_postgres_health", return_value=True),
        patch("infrastructure.neo4j_driver.check_neo4j_health", return_value=True),
    ):
        data = client.get("/health").json()
    assert "status" in data
    assert "postgres" in data
    assert "neo4j" in data
    assert "version" in data


def test_health_degraded_when_postgres_down():
    with (
        patch("infrastructure.database.check_postgres_health", return_value=False),
        patch("infrastructure.neo4j_driver.check_neo4j_health", return_value=True),
    ):
        data = client.get("/health").json()
    assert data["status"] == "degraded"
    assert data["postgres"] is False
