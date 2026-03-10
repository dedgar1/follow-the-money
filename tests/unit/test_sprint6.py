"""
Sprint 6 unit tests — Neo4j multi-hop network queries + GraphQL schema.

Covers:
  - NetworkQueryService.get_donor_network (mocked Neo4j driver)
  - NetworkQueryService.get_rep_network   (mocked Neo4j driver)
  - _build_graph deduplication logic
  - GraphQL schema: hello, representative, donor, repNetwork, donorNetwork
  - REST network endpoints: /network returns 200 or 404
  - Architecture: adapters/neo4j imports no domain framework code
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest
from fastapi.testclient import TestClient

from adapters.neo4j.network_query import NetworkQueryService, _build_graph


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_driver(side_effects: list):
    """
    Build a mock Neo4j driver whose session.run() returns successive values
    from `side_effects` (one value per call, in order).
    """
    mock_session = MagicMock()
    mock_driver = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    run_results = []
    for effect in side_effects:
        m = MagicMock()
        if isinstance(effect, dict):
            # single() returns a dict-like
            m.single.return_value = effect
            m.data.return_value = [effect]
        elif isinstance(effect, list):
            m.single.return_value = effect[0] if effect else None
            m.data.return_value = effect
        else:
            m.single.return_value = effect
            m.data.return_value = []
        run_results.append(m)

    mock_session.run.side_effect = run_results
    return mock_driver, mock_session


# ── _build_graph ──────────────────────────────────────────────────────────────


class TestBuildGraph:
    def test_deduplicates_nodes(self):
        center = {"id": "A", "type": "rep", "label": "Alice", "is_center": True}
        hop1 = [{"id": "D1", "type": "donor", "label": "PAC1", "is_center": False}]
        hop2 = [{"id": "D1", "type": "donor", "label": "PAC1", "is_center": False}]  # dup
        result = _build_graph(center, hop1, [], hop2, [])
        ids = [n["id"] for n in result["nodes"]]
        assert ids.count("D1") == 1

    def test_deduplicates_edges(self):
        center = {"id": "A", "type": "rep", "label": "Alice", "is_center": True}
        e = {"source": "D1", "target": "A", "total_cents": 1000, "cycles": [2024]}
        result = _build_graph(center, [], [e], [], [e])  # same edge twice
        assert len(result["edges"]) == 1

    def test_center_node_is_first(self):
        center = {"id": "C", "type": "rep", "label": "C", "is_center": True}
        hop1 = [{"id": "D1", "type": "donor", "label": "D1", "is_center": False}]
        result = _build_graph(center, hop1, [], [], [])
        assert result["nodes"][0]["id"] == "C"

    def test_returns_all_hops(self):
        center = {"id": "C", "type": "rep", "label": "C", "is_center": True}
        hop1 = [{"id": "D1", "type": "donor", "label": "D1", "is_center": False}]
        hop2 = [{"id": "R2", "type": "rep", "label": "R2", "is_center": False}]
        e1 = {"source": "D1", "target": "C", "total_cents": 100, "cycles": [2024]}
        e2 = {"source": "D1", "target": "R2", "total_cents": 50, "cycles": [2024]}
        result = _build_graph(center, hop1, [e1], hop2, [e2])
        assert len(result["nodes"]) == 3
        assert len(result["edges"]) == 2


# ── NetworkQueryService.get_donor_network ─────────────────────────────────────


class TestGetDonorNetwork:
    PATCH = "adapters.neo4j.network_query.get_driver"

    def test_returns_empty_when_center_not_found(self):
        mock_driver, _ = _make_driver([None])
        with patch(self.PATCH, return_value=mock_driver):
            result = NetworkQueryService().get_donor_network("DONOR_X")
        assert result == {"nodes": [], "edges": []}

    def test_returns_nodes_and_edges_for_known_donor(self):
        center = {"id": "D1", "label": "Tech PAC", "donor_type": "pac"}
        rep_rows = [
            {"id": "R1", "label": "Jane Smith", "party": "D", "chamber": "house",
             "state": "CA", "total_cents": 50000, "cycles": [2024]},
        ]
        hop2_rows = [
            {"id": "D2", "label": "Finance PAC", "donor_type": "pac",
             "rep_id": "R1", "total_cents": 20000, "cycles": [2024]},
        ]
        mock_driver, _ = _make_driver([center, rep_rows, hop2_rows])
        with patch(self.PATCH, return_value=mock_driver):
            result = NetworkQueryService().get_donor_network("D1")

        node_ids = {n["id"] for n in result["nodes"]}
        assert "D1" in node_ids   # center
        assert "R1" in node_ids   # hop-1 rep
        assert "D2" in node_ids   # hop-2 sibling donor

        assert any(e["source"] == "D1" and e["target"] == "R1" for e in result["edges"])
        assert any(e["source"] == "D2" and e["target"] == "R1" for e in result["edges"])

    def test_center_node_is_marked_is_center(self):
        center = {"id": "D1", "label": "PAC", "donor_type": "pac"}
        mock_driver, _ = _make_driver([center, [], []])
        with patch(self.PATCH, return_value=mock_driver):
            result = NetworkQueryService().get_donor_network("D1")
        center_node = next(n for n in result["nodes"] if n["id"] == "D1")
        assert center_node["is_center"] is True

    def test_hop2_skipped_when_no_rep_ids(self):
        center = {"id": "D1", "label": "PAC", "donor_type": "pac"}
        mock_driver, mock_session = _make_driver([center, [], []])
        with patch(self.PATCH, return_value=mock_driver):
            NetworkQueryService().get_donor_network("D1")
        # run() called twice: center lookup + rep rows (hop2 skipped — no rep_ids)
        assert mock_session.run.call_count == 2


# ── NetworkQueryService.get_rep_network ───────────────────────────────────────


class TestGetRepNetwork:
    PATCH = "adapters.neo4j.network_query.get_driver"

    def test_returns_empty_when_rep_not_found(self):
        mock_driver, _ = _make_driver([None])
        with patch(self.PATCH, return_value=mock_driver):
            result = NetworkQueryService().get_rep_network("REP_X")
        assert result == {"nodes": [], "edges": []}

    def test_returns_nodes_and_edges_for_known_rep(self):
        center = {"id": "R1", "label": "Jane Smith", "party": "D",
                  "chamber": "house", "state": "CA"}
        donor_rows = [
            {"id": "D1", "label": "Tech PAC", "donor_type": "pac",
             "total_cents": 80000, "cycles": [2024]},
        ]
        hop2_rows = [
            {"id": "R2", "label": "Bob Jones", "party": "R", "chamber": "house",
             "state": "TX", "donor_id": "D1", "total_cents": 40000, "cycles": [2024]},
        ]
        mock_driver, _ = _make_driver([center, donor_rows, hop2_rows])
        with patch(self.PATCH, return_value=mock_driver):
            result = NetworkQueryService().get_rep_network("R1")

        node_ids = {n["id"] for n in result["nodes"]}
        assert "R1" in node_ids
        assert "D1" in node_ids
        assert "R2" in node_ids

        assert any(e["source"] == "D1" and e["target"] == "R1" for e in result["edges"])
        assert any(e["source"] == "D1" and e["target"] == "R2" for e in result["edges"])

    def test_rep_center_node_type_is_rep(self):
        center = {"id": "R1", "label": "Jane", "party": "D",
                  "chamber": "house", "state": "CA"}
        mock_driver, _ = _make_driver([center, [], []])
        with patch(self.PATCH, return_value=mock_driver):
            result = NetworkQueryService().get_rep_network("R1")
        center_node = result["nodes"][0]
        assert center_node["type"] == "rep"
        assert center_node["is_center"] is True


# ── GraphQL schema ────────────────────────────────────────────────────────────


class TestGraphQLSchema:
    """Integration tests using the FastAPI test client with mocked DB."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from apps.api.main import app
        from infrastructure.database import get_db
        from adapters.postgres.orm_models import CanonicalRepRow, CanonicalDonorRow

        mock_db = MagicMock()
        mock_db.get.return_value = None
        mock_db.execute.return_value.scalar.return_value = 0
        mock_db.execute.return_value.fetchall.return_value = []

        app.dependency_overrides[get_db] = lambda: mock_db
        self.client = TestClient(app)
        self.mock_db = mock_db

        yield

        app.dependency_overrides.clear()

    def test_hello_query(self):
        r = self.client.post("/graphql", json={"query": "{ hello }"})
        assert r.status_code == 200
        assert r.json()["data"]["hello"] == "Follow the Money GraphQL API — v0.1.0"

    def test_representative_returns_null_when_not_found(self):
        r = self.client.post(
            "/graphql",
            json={"query": '{ representative(id: "X") { id fullName } }'},
        )
        assert r.status_code == 200
        assert r.json()["data"]["representative"] is None

    def test_representative_returns_profile_when_found(self):
        from adapters.postgres.orm_models import CanonicalRepRow
        rep = CanonicalRepRow(
            id="R1", full_name="Jane Smith", party="D",
            chamber="house", state="CA", district="CA-12",
            bioguide_id="S000001", fec_candidate_id=None,
        )
        self.mock_db.get.return_value = rep
        r = self.client.post(
            "/graphql",
            json={"query": '{ representative(id: "R1") { id fullName party state } }'},
        )
        assert r.status_code == 200
        data = r.json()["data"]["representative"]
        assert data["id"] == "R1"
        assert data["fullName"] == "Jane Smith"
        assert data["party"] == "D"

    def test_donor_returns_null_when_not_found(self):
        r = self.client.post(
            "/graphql",
            json={"query": '{ donor(id: "X") { id name } }'},
        )
        assert r.status_code == 200
        assert r.json()["data"]["donor"] is None

    def test_rep_network_returns_empty_when_neo4j_unavailable(self):
        r = self.client.post(
            "/graphql",
            json={"query": '{ repNetwork(repId: "R1") { nodes { id } edges { source } } }'},
        )
        assert r.status_code == 200
        data = r.json()["data"]["repNetwork"]
        assert data["nodes"] == []
        assert data["edges"] == []

    def test_donor_network_returns_empty_when_neo4j_unavailable(self):
        r = self.client.post(
            "/graphql",
            json={"query": '{ donorNetwork(donorId: "D1") { nodes { id nodeType } edges { source target } } }'},
        )
        assert r.status_code == 200
        data = r.json()["data"]["donorNetwork"]
        assert data["nodes"] == []


# ── REST network endpoints ────────────────────────────────────────────────────


class TestRestNetworkEndpoints:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from apps.api.main import app
        from infrastructure.database import get_db

        mock_db = MagicMock()
        mock_db.get.return_value = None
        app.dependency_overrides[get_db] = lambda: mock_db
        self.client = TestClient(app)
        self.mock_db = mock_db
        yield
        app.dependency_overrides.clear()

    def test_rep_network_returns_404_when_rep_not_found(self):
        r = self.client.get("/v1/representatives/NOPE/network")
        assert r.status_code == 404

    def test_donor_network_returns_404_when_donor_not_found(self):
        r = self.client.get("/v1/donors/NOPE/network")
        assert r.status_code == 404

    def test_rep_network_returns_empty_graph_when_neo4j_unavailable(self):
        from adapters.postgres.orm_models import CanonicalRepRow
        self.mock_db.get.return_value = CanonicalRepRow(
            id="R1", full_name="Jane Smith", party="D",
            chamber="house", state="CA", district=None,
            bioguide_id=None, fec_candidate_id=None,
        )
        r = self.client.get("/v1/representatives/R1/network")
        assert r.status_code == 200
        assert r.json() == {"nodes": [], "edges": []}

    def test_donor_network_returns_empty_graph_when_neo4j_unavailable(self):
        from adapters.postgres.orm_models import CanonicalDonorRow
        self.mock_db.get.return_value = CanonicalDonorRow(
            id="D1", name="Tech PAC", donor_type="pac",
            industry="technology", state="CA", fec_ids="[]",
        )
        r = self.client.get("/v1/donors/D1/network")
        assert r.status_code == 200
        assert r.json() == {"nodes": [], "edges": []}


# ── Architecture purity ───────────────────────────────────────────────────────


def test_network_query_imports_no_sqlalchemy():
    import importlib, inspect
    src = inspect.getsource(importlib.import_module("adapters.neo4j.network_query"))
    assert "sqlalchemy" not in src
    assert "fastapi" not in src


def test_network_query_imports_no_domain_models():
    import importlib, inspect
    src = inspect.getsource(importlib.import_module("adapters.neo4j.network_query"))
    assert "from domain" not in src
    assert "import domain" not in src
