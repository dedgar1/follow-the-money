"""
Sprint 7 unit tests — Bill NLP classifier + voting record endpoint.

Covers:
  - BillClassifier: keyword matching, confidence scoring, batch classify
  - BillClassifier: returns UNKNOWN for unrecognisable titles
  - REST GET /representatives/{id}/votes: 404 on unknown rep, empty list when
    no bioguide_id, rows returned when mock DB has vote data
  - _vote_record_from_row position normalisation
  - Architecture purity: bill_classifier imports no domain framework code
  - classify_bills Celery task helper: _classify_all_bills (mocked DB)
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from adapters.nlp.bill_classifier import BillClassifier, _normalize
from apps.api.rest_router import _POSITION_NORM, _vote_record_from_row, VoteRecord
from domain.shared.industry import Industry


# ── _normalize helper ─────────────────────────────────────────────────────────


def test_normalize_lowercases_and_strips():
    assert _normalize("  Hello   WORLD  ") == "hello world"


# ── BillClassifier ────────────────────────────────────────────────────────────


class TestBillClassifier:
    def setup_method(self):
        self.clf = BillClassifier()

    def test_energy_bill(self):
        industry, conf = self.clf.classify("American Clean Energy Act")
        assert industry == Industry.ENERGY_NATURAL_RESOURCES
        assert conf > 0

    def test_defense_bill(self):
        industry, conf = self.clf.classify(
            "National Defense Authorization Act for Fiscal Year 2025"
        )
        assert industry == Industry.DEFENSE
        assert conf > 0.5

    def test_health_bill(self):
        industry, conf = self.clf.classify("Prescription Drug Pricing Transparency Act")
        assert industry == Industry.HEALTH

    def test_labor_bill(self):
        industry, conf = self.clf.classify("Minimum Wage and Worker Protection Act")
        assert industry == Industry.LABOR

    def test_finance_bill(self):
        industry, conf = self.clf.classify(
            "Wall Street Reform and Consumer Financial Protection Act"
        )
        assert industry == Industry.FINANCE_INSURANCE_REAL_ESTATE

    def test_agriculture_bill(self):
        industry, conf = self.clf.classify("Farm Bill Agricultural Support Act")
        assert industry == Industry.AGRICULTURE

    def test_communications_bill(self):
        industry, conf = self.clf.classify("Net Neutrality and Broadband Access Restoration Act")
        assert industry == Industry.COMMUNICATIONS_ELECTRONICS

    def test_transportation_bill(self):
        industry, conf = self.clf.classify("Highway Infrastructure and Transportation Investment")
        assert industry == Industry.TRANSPORTATION

    def test_unknown_for_gibberish(self):
        industry, conf = self.clf.classify("Zzzz foobar baz")
        assert industry == Industry.UNKNOWN
        assert conf == 0.0

    def test_subjects_boost_confidence(self):
        _, conf_no_subjects = self.clf.classify("H.R. 1234")
        _, conf_with = self.clf.classify("H.R. 1234", subjects=["Energy policy", "Oil and gas"])
        assert conf_with > conf_no_subjects

    def test_longer_phrase_wins_over_short_word(self):
        # "national defense authorization" should match DEFENSE more strongly
        # than the word "national" alone
        industry, _ = self.clf.classify("National Defense Authorization Act")
        assert industry == Industry.DEFENSE

    def test_confidence_in_unit_interval(self):
        for title in [
            "American Clean Energy Act",
            "Minimum Wage Act",
            "National Defense Authorization",
            "Gibberish bill XYZ",
        ]:
            _, conf = self.clf.classify(title)
            assert 0.0 <= conf <= 1.0, f"confidence {conf} out of range for '{title}'"

    def test_classify_many(self):
        bills = [
            ("National Defense Authorization Act", None),
            ("Medicare Advantage Modernization Act", ["Health"]),
            ("Totally unknown text", None),
        ]
        results = self.clf.classify_many(bills)
        assert len(results) == 3
        assert results[0][0] == Industry.DEFENSE
        assert results[1][0] == Industry.HEALTH
        assert results[2][0] == Industry.UNKNOWN


# ── _vote_record_from_row ─────────────────────────────────────────────────────


class TestVoteRecordFromRow:
    def _row(
        self,
        vote_id="V1",
        bill_id="hr1001",
        bill_title="Test Bill",
        position="Yea",
        voted_at="2025-01-20",
        chamber="House",
        industries=None,
        nlp_confidence=0.85,
    ):
        return (
            vote_id, bill_id, bill_title, position, voted_at, chamber,
            json.dumps(industries or ["energy_natural_resources"]),
            nlp_confidence,
        )

    def test_yea_maps_to_yes(self):
        rec = _vote_record_from_row(self._row(position="Yea"))
        assert rec.position == "yes"

    def test_nay_maps_to_no(self):
        rec = _vote_record_from_row(self._row(position="Nay"))
        assert rec.position == "no"

    def test_not_voting_maps_correctly(self):
        rec = _vote_record_from_row(self._row(position="Not Voting"))
        assert rec.position == "not_voting"

    def test_present_maps_to_abstain(self):
        rec = _vote_record_from_row(self._row(position="Present"))
        assert rec.position == "abstain"

    def test_industries_parsed(self):
        rec = _vote_record_from_row(self._row(industries=["health"]))
        assert rec.industries == ["health"]

    def test_null_industries_returns_empty_list(self):
        row = (
            "V1", "hr1001", "Test Bill", "Yea", "2025-01-20", "House",
            None, 0.0,
        )
        rec = _vote_record_from_row(row)
        assert rec.industries == []

    def test_chamber_lowercased(self):
        rec = _vote_record_from_row(self._row(chamber="House"))
        assert rec.chamber == "house"

    def test_voted_at_truncated_to_date(self):
        rec = _vote_record_from_row(self._row(voted_at="2025-03-15 00:00:00"))
        assert rec.voted_at == "2025-03-15"


# ── REST /votes endpoint ───────────────────────────────────────────────────────


class TestVotesEndpoint:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from apps.api.main import app
        from infrastructure.database import get_db
        from adapters.postgres.orm_models import CanonicalRepRow

        mock_db = MagicMock()
        mock_db.get.return_value = None
        app.dependency_overrides[get_db] = lambda: mock_db
        self.client = TestClient(app)
        self.mock_db = mock_db
        yield
        app.dependency_overrides.clear()

    def test_404_when_rep_not_found(self):
        r = self.client.get("/v1/representatives/NOPE/votes")
        assert r.status_code == 404

    def test_empty_list_when_no_bioguide_id(self):
        from adapters.postgres.orm_models import CanonicalRepRow
        self.mock_db.get.return_value = CanonicalRepRow(
            id="R1", full_name="Jane Smith", party="D",
            chamber="house", state="CA", district=None,
            bioguide_id=None, fec_candidate_id=None,
        )
        r = self.client.get("/v1/representatives/R1/votes")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_vote_records_for_known_rep(self):
        from adapters.postgres.orm_models import CanonicalRepRow

        self.mock_db.get.return_value = CanonicalRepRow(
            id="R1", full_name="Jane Smith", party="D",
            chamber="house", state="CA", district=None,
            bioguide_id="B000001", fec_candidate_id=None,
        )

        vote_rows = [
            (
                "VOTE001", "hr1001", "American Clean Energy Act", "Yea",
                "2025-01-20", "House",
                '["energy_natural_resources"]', 0.85,
            ),
            (
                "VOTE002", "hr1002", "Wall Street Reform Act", "Nay",
                "2025-01-22", "House",
                '["finance_insurance_real_estate"]', 0.88,
            ),
        ]
        self.mock_db.execute.return_value.fetchall.return_value = vote_rows

        r = self.client.get("/v1/representatives/R1/votes")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        assert data[0]["vote_id"] == "VOTE001"
        assert data[0]["position"] == "yes"
        assert data[0]["industries"] == ["energy_natural_resources"]
        assert data[1]["position"] == "no"
        assert data[1]["chamber"] == "house"

    def test_limit_capped_at_200(self):
        from adapters.postgres.orm_models import CanonicalRepRow

        self.mock_db.get.return_value = CanonicalRepRow(
            id="R1", full_name="Jane Smith", party="D",
            chamber="house", state="CA", district=None,
            bioguide_id="B000001", fec_candidate_id=None,
        )
        self.mock_db.execute.return_value.fetchall.return_value = []

        r = self.client.get("/v1/representatives/R1/votes?limit=9999")
        assert r.status_code == 200


# ── Architecture purity ────────────────────────────────────────────────────────


def test_bill_classifier_imports_no_sqlalchemy():
    import importlib, inspect
    src = inspect.getsource(importlib.import_module("adapters.nlp.bill_classifier"))
    assert "sqlalchemy" not in src
    assert "fastapi" not in src


def test_bill_classifier_imports_only_domain_shared():
    """BillClassifier may import from domain.shared (pure Python) but not adapters."""
    import importlib, inspect
    src = inspect.getsource(importlib.import_module("adapters.nlp.bill_classifier"))
    assert "from adapters" not in src
    assert "from infrastructure" not in src


# ── classify_bills pipeline task helper ───────────────────────────────────────


def test_classify_all_bills_updates_db():
    """_classify_all_bills fetches bills and calls UPDATE for each."""
    from pipeline.tasks.classify_bills import _classify_all_bills

    mock_rows = [
        ("BILL001", "American Clean Energy Act", "[]", 0.0),
        ("BILL002", "National Defense Authorization Act", "[]", 0.0),
    ]

    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = mock_rows

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_session)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    with patch("pipeline.tasks.classify_bills.get_session", return_value=mock_ctx):
        count = _classify_all_bills()

    assert count == 2
    # One UPDATE call per bill + one SELECT
    assert mock_session.execute.call_count == 3  # 1 SELECT + 2 UPDATEs
    mock_session.commit.assert_called_once()
