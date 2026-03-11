"""
Integration tests for REST endpoints and GraphQL.

Sprint 5: representatives, donors, and search endpoints are now implemented.
Sprint 7: /votes endpoint implemented — returns 404 for unknown rep.
Sprint 8: /correlations endpoint implemented — returns 404 for unknown rep.
Remaining stubs (zip, compare, export) still return 501.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from adapters.postgres.orm_models import CanonicalDonorRow, CanonicalRepRow
from apps.api.main import app
from infrastructure.database import get_db


# ── DB mock setup ─────────────────────────────────────────────────────────────


def _make_mock_db() -> MagicMock:
    """Fluent SQLAlchemy Session mock — all chains resolve to empty results."""
    m = MagicMock()
    m.get.return_value = None
    m.execute.return_value.scalar.return_value = 0
    m.execute.return_value.fetchall.return_value = []

    # Chain mock: query().filter().order_by().limit().all() → []
    chain = MagicMock()
    chain.all.return_value = []
    chain.filter.return_value = chain
    chain.filter_by.return_value = chain
    chain.order_by.return_value = chain
    chain.limit.return_value = chain
    m.query.return_value = chain
    return m


_mock_db = _make_mock_db()
app.dependency_overrides[get_db] = lambda: _mock_db

client = TestClient(app)


# ── REST — still-unimplemented endpoints (future sprints) ─────────────────────


@pytest.mark.parametrize("path", [
    # /votes (Sprint 7) and /correlations (Sprint 8) are implemented —
    # they return 404 for unknown rep, not 501
    "/v1/zip/90210",
    "/v1/compare?ids=rep1,rep2",
    "/v1/export/rep1.csv",
])
def test_unimplemented_rest_endpoints_return_501(path: str):
    response = client.get(path)
    assert response.status_code == 501
    assert "detail" in response.json()


def test_votes_returns_404_for_unknown_rep():
    """Sprint 7: /votes endpoint is implemented — returns 404 (not 501) for unknown rep."""
    response = client.get("/v1/representatives/rep1/votes")
    assert response.status_code == 404


def test_correlations_returns_404_for_unknown_rep():
    """Sprint 8: /correlations endpoint is implemented — returns 404 for unknown rep."""
    response = client.get("/v1/representatives/rep1/correlations")
    assert response.status_code == 404


# ── REST — representatives (Sprint 5) ─────────────────────────────────────────


def test_list_representatives_returns_200_with_empty_list():
    response = client.get("/v1/representatives")
    assert response.status_code == 200
    assert response.json() == []


def test_list_representatives_accepts_filter_params():
    for params in ["?state=CA", "?chamber=house", "?party=D", "?state=TX&chamber=senate&party=R"]:
        assert client.get(f"/v1/representatives{params}").status_code == 200


def test_get_representative_returns_404_when_not_found():
    response = client.get("/v1/representatives/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Representative not found"


def test_get_representative_returns_profile_when_found():
    rep_row = CanonicalRepRow(
        id="rep1",
        full_name="Jane Smith",
        party="D",
        chamber="house",
        state="CA",
        district="CA-12",
        bioguide_id="S000001",
        fec_candidate_id=None,
    )
    _mock_db.get.return_value = rep_row
    try:
        response = client.get("/v1/representatives/rep1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "rep1"
        assert data["full_name"] == "Jane Smith"
        assert data["party"] == "D"
        assert data["total_raised_cents"] == 0
        assert data["top_industries"] == []
        assert data["top_donors"] == []
    finally:
        _mock_db.get.return_value = None


# ── REST — donors (Sprint 5) ──────────────────────────────────────────────────


def test_get_donor_returns_404_when_not_found():
    response = client.get("/v1/donors/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Donor not found"


def test_get_donor_returns_profile_when_found():
    donor_row = CanonicalDonorRow(
        id="donor1",
        name="Tech PAC",
        donor_type="pac",
        industry="technology",
        state="CA",
        fec_ids="[]",
    )
    _mock_db.get.return_value = donor_row
    try:
        response = client.get("/v1/donors/donor1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "donor1"
        assert data["name"] == "Tech PAC"
        assert data["total_given_cents"] == 0
    finally:
        _mock_db.get.return_value = None


def test_get_donor_recipients_returns_404_when_donor_not_found():
    response = client.get("/v1/donors/nonexistent/recipients")
    assert response.status_code == 404


def test_get_donor_recipients_returns_list_when_found():
    donor_row = CanonicalDonorRow(
        id="donor1", name="Tech PAC", donor_type="pac",
        industry="technology", state="CA", fec_ids="[]",
    )
    _mock_db.get.return_value = donor_row
    try:
        response = client.get("/v1/donors/donor1/recipients")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    finally:
        _mock_db.get.return_value = None


# ── REST — search (Sprint 5) ──────────────────────────────────────────────────


def test_search_returns_200_with_empty_results():
    response = client.get("/v1/search?q=smith")
    assert response.status_code == 200
    assert response.json() == []


def test_search_requires_q_param():
    response = client.get("/v1/search")
    # FastAPI returns 422 for missing required query param
    assert response.status_code == 422


# ── GraphQL ───────────────────────────────────────────────────────────────────


def test_graphql_hello_query():
    response = client.post("/graphql", json={"query": "{ hello }"})
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["hello"] == "Follow the Money GraphQL API — v0.1.0"


def test_graphql_introspection():
    response = client.post("/graphql", json={"query": "{ __typename }"})
    assert response.status_code == 200


# ── Health ────────────────────────────────────────────────────────────────────


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
