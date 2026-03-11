"""
Sprint 9 unit tests — Compare · CSV Export · ZIP lookup · Widget · Shareable URLs.

Covers:
  - GET /v1/compare: 422 (< 2 IDs), 422 (> 5 IDs), 404 (unknown rep), 200 with data
  - GET /v1/export/{rep_id}.csv: 404, 200 returns CSV bytes
  - GET /v1/zip/{zipcode}: 422 for non-numeric, 200 returns list
  - GET /v1/widget/{rep_id}: 404, 200 returns HTML
  - _zip_to_state helper: spot-checks for known ZIP codes
  - Architecture: new endpoint functions import only from allowed modules
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from adapters.postgres.orm_models import (
    AlignmentScoreRow,
    CanonicalDonorRow,
    CanonicalRepRow,
)
from apps.api.main import app
from infrastructure.database import get_db


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_rep(rep_id: str = "REP001", full_name: str = "Jane Smith",
              party: str = "D", chamber: str = "house",
              state: str = "CA") -> CanonicalRepRow:
    return CanonicalRepRow(
        id=rep_id, full_name=full_name, party=party,
        chamber=chamber, state=state, bioguide_id=None,
    )


def _make_donor(donor_id: str = "DON001", name: str = "Energy PAC",
                industry: str = "energy_natural_resources") -> CanonicalDonorRow:
    return CanonicalDonorRow(
        id=donor_id, name=name, donor_type="pac",
        industry=industry, state="TX", fec_ids="[]",
    )


def _client_with_db(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False), app


# ── _zip_to_state helper ──────────────────────────────────────────────────────


def test_zip_to_state_california():
    from apps.api.rest_router import _zip_to_state
    assert _zip_to_state("90210") == "CA"


def test_zip_to_state_new_york():
    from apps.api.rest_router import _zip_to_state
    assert _zip_to_state("10001") == "NY"


def test_zip_to_state_texas():
    from apps.api.rest_router import _zip_to_state
    assert _zip_to_state("75001") == "TX"


def test_zip_to_state_invalid_returns_none():
    from apps.api.rest_router import _zip_to_state
    assert _zip_to_state("abc12") is None
    assert _zip_to_state("1234") is None


# ── GET /zip/{zipcode} ────────────────────────────────────────────────────────


def test_zip_returns_422_for_nonnumeric():
    session = MagicMock()
    client, app_ = _client_with_db(session)
    try:
        resp = client.get("/v1/zip/ABCDE")
    finally:
        app_.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 422


def test_zip_returns_200_empty_list_for_unknown_zip():
    session = MagicMock()
    chain = MagicMock()
    chain.filter.return_value = chain
    chain.order_by.return_value = chain
    chain.all.return_value = []
    session.query.return_value = chain

    client, app_ = _client_with_db(session)
    try:
        resp = client.get("/v1/zip/90210")
    finally:
        app_.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_zip_returns_reps_for_known_state():
    rep = _make_rep(state="CA")
    session = MagicMock()
    chain = MagicMock()
    chain.filter.return_value = chain
    chain.order_by.return_value = chain
    chain.all.return_value = [rep]
    session.query.return_value = chain

    client, app_ = _client_with_db(session)
    try:
        resp = client.get("/v1/zip/90210")
    finally:
        app_.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["state"] == "CA"


# ── GET /compare ──────────────────────────────────────────────────────────────


def test_compare_returns_422_for_single_id():
    session = MagicMock()
    session.get.return_value = None
    client, app_ = _client_with_db(session)
    try:
        resp = client.get("/v1/compare?ids=rep1")
    finally:
        app_.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 422


def test_compare_returns_422_for_too_many_ids():
    session = MagicMock()
    client, app_ = _client_with_db(session)
    try:
        resp = client.get("/v1/compare?ids=a,b,c,d,e,f")
    finally:
        app_.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 422


def test_compare_returns_404_for_unknown_rep():
    session = MagicMock()
    session.get.return_value = None
    client, app_ = _client_with_db(session)
    try:
        resp = client.get("/v1/compare?ids=rep1,rep2")
    finally:
        app_.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 404


def test_compare_returns_200_with_two_reps():
    rep1 = _make_rep("REP001", "Jane Smith", state="CA")
    rep2 = _make_rep("REP002", "John Doe", party="R", state="TX")

    session = MagicMock()
    session.get.side_effect = lambda model, rep_id: (
        rep1 if rep_id == "REP001" else rep2 if rep_id == "REP002" else None
    )

    scalar_mock = MagicMock()
    scalar_mock.scalar.return_value = 0
    session.execute.return_value = scalar_mock
    session.execute.return_value.scalar.return_value = 0
    session.execute.return_value.fetchall.return_value = []

    score_chain = MagicMock()
    score_chain.filter_by.return_value = score_chain
    score_chain.order_by.return_value = score_chain
    score_chain.all.return_value = []
    session.query.return_value = score_chain

    client, app_ = _client_with_db(session)
    try:
        resp = client.get("/v1/compare?ids=REP001,REP002")
    finally:
        app_.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 200
    data = resp.json()
    assert data["rep_ids"] == ["REP001", "REP002"]
    assert len(data["reps"]) == 2
    assert isinstance(data["shared_donors"], list)


def test_compare_shared_donors_intersected():
    """Shared donors appear only if they funded ALL reps."""
    rep1 = _make_rep("R1")
    rep2 = _make_rep("R2")
    donor = _make_donor("D1")

    def _get(model, key):
        if key == "R1": return rep1
        if key == "R2": return rep2
        if key == "D1": return donor
        return None

    # execute is called in this order per rep:
    #   (1) scalar — total_raised
    #   (2) fetchall — industry_rows   → (industry, cents) 2-elem
    #   (3) fetchall — top_donor_rows  → (id, name, type, cents) 4-elem
    #   (4) fetchall — donor_map       → (donor_id, cents) 2-elem
    _call = [0]

    def _execute(sql, params=None):
        _call[0] += 1
        result = MagicMock()
        pos = (_call[0] - 1) % 4   # 0=scalar, 1=industries, 2=top_donors, 3=donor_map
        result.scalar.return_value = 0
        result.fetchall.return_value = [] if pos in (1, 2) else [("D1", 10_000)]
        return result

    session = MagicMock()
    session.get.side_effect = _get
    session.execute.side_effect = _execute

    score_chain = MagicMock()
    score_chain.filter_by.return_value = score_chain
    score_chain.order_by.return_value = score_chain
    score_chain.all.return_value = []
    session.query.return_value = score_chain

    client, app_ = _client_with_db(session)
    try:
        resp = client.get("/v1/compare?ids=R1,R2")
    finally:
        app_.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["shared_donors"]) == 1
    assert data["shared_donors"][0]["donor_id"] == "D1"


# ── GET /export/{rep_id}.csv ──────────────────────────────────────────────────


def test_export_returns_404_for_unknown_rep():
    session = MagicMock()
    session.get.return_value = None
    client, app_ = _client_with_db(session)
    try:
        resp = client.get("/v1/export/UNKNOWN.csv")
    finally:
        app_.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 404


def test_export_returns_csv_for_known_rep():
    rep = _make_rep("REP001", "Jane Smith")
    session = MagicMock()
    session.get.return_value = rep
    session.execute.return_value.scalar.return_value = 0
    session.execute.return_value.fetchall.return_value = []

    score_chain = MagicMock()
    score_chain.filter_by.return_value = score_chain
    score_chain.order_by.return_value = score_chain
    score_chain.all.return_value = []
    session.query.return_value = score_chain

    client, app_ = _client_with_db(session)
    try:
        resp = client.get("/v1/export/REP001.csv")
    finally:
        app_.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers.get("content-disposition", "")
    body = resp.text
    assert "Follow the Money" in body
    assert "Jane Smith" in body
    assert "representative" in body


def test_export_csv_contains_alignment_scores():
    rep = _make_rep("REP001", "Jane Smith")
    score = AlignmentScoreRow(
        id="sc01", rep_id="REP001", donor_id="D1",
        industry="energy_natural_resources", score=0.65, confidence="medium",
        evidence_count=12, before_score=0.40, after_score=0.65,
        shift=0.25, p_value=0.03, methodology_url="/docs/methodology",
        computed_at="2026-03-10",
    )
    session = MagicMock()
    session.get.return_value = rep
    session.execute.return_value.scalar.return_value = 0
    session.execute.return_value.fetchall.return_value = []

    score_chain = MagicMock()
    score_chain.filter_by.return_value = score_chain
    score_chain.order_by.return_value = score_chain
    score_chain.all.return_value = [score]
    session.query.return_value = score_chain

    client, app_ = _client_with_db(session)
    try:
        resp = client.get("/v1/export/REP001.csv")
    finally:
        app_.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 200
    body = resp.text
    assert "alignment_score" in body
    assert "energy_natural_resources" in body


# ── GET /widget/{rep_id} ──────────────────────────────────────────────────────


def test_widget_returns_404_for_unknown_rep():
    session = MagicMock()
    session.get.return_value = None
    client, app_ = _client_with_db(session)
    try:
        resp = client.get("/v1/widget/UNKNOWN")
    finally:
        app_.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 404


def test_widget_returns_html_for_known_rep():
    rep = _make_rep("REP001", "Jane Smith")
    session = MagicMock()
    session.get.return_value = rep
    session.execute.return_value.scalar.return_value = 5_000_000_00
    session.execute.return_value.fetchall.return_value = []

    client, app_ = _client_with_db(session)
    try:
        resp = client.get("/v1/widget/REP001")
    finally:
        app_.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Jane Smith" in resp.text
    assert "$5.0M" in resp.text


def test_widget_dark_theme():
    rep = _make_rep("REP001", "Jane Smith")
    session = MagicMock()
    session.get.return_value = rep
    session.execute.return_value.scalar.return_value = 0
    session.execute.return_value.fetchall.return_value = []

    client, app_ = _client_with_db(session)
    try:
        resp = client.get("/v1/widget/REP001?theme=dark")
    finally:
        app_.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 200
    assert "#1a1a2e" in resp.text


# ── Architecture purity ───────────────────────────────────────────────────────


def test_zip_to_state_is_pure_python():
    """_zip_to_state uses no I/O — all computations are pure integer comparisons."""
    from apps.api.rest_router import _zip_to_state
    import inspect
    source = inspect.getsource(_zip_to_state)
    for forbidden in ("import", "open", "requests", "httpx"):
        assert forbidden not in source, f"_zip_to_state must not use {forbidden}"
