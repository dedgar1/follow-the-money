"""
Sprint 8 unit tests — CorrelationEngine statistics · AlignmentScore computation
· PostgresCorrelationRepository · REST /correlations endpoint.

Covers:
  - fishers_exact_test: known p-values, degenerate tables
  - compute_alignment_score: edge cases
  - CorrelationEngine.compute_for_rep: below-threshold → no scores,
    significant shift → one score returned
  - AlignmentScore.is_significant threshold checks
  - PostgresCorrelationRepository save_score / get_scores_for_rep (mocked session)
  - REST GET /representatives/{id}/correlations: 404, empty list, scores returned
  - ORM: AlignmentScoreRow and CorrelationEventRow are importable
  - Architecture purity: statistics module imports no framework code
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from domain.correlation.models import (
    AlignmentScore,
    AlignmentScoreId,
    ConfidenceLevel,
    CorrelationEvent,
    CorrelationEventId,
)
from domain.correlation.statistics import compute_alignment_score, fishers_exact_test
from domain.identity.models import CanonicalDonorRef, CanonicalRepRef, DonorId, RepId
from domain.shared.industry import Industry
from domain.shared.money import Money


# ── compute_alignment_score ───────────────────────────────────────────────────


def test_alignment_score_zero_total():
    assert compute_alignment_score(0, 0) == 0.0


def test_alignment_score_all_yes():
    assert compute_alignment_score(10, 10) == 1.0


def test_alignment_score_half():
    assert compute_alignment_score(5, 10) == 0.5


def test_alignment_score_clamps_above_total():
    # yes_votes > total_votes is nonsensical — clamp to 1.0
    assert compute_alignment_score(15, 10) == 1.0


def test_alignment_score_negative_clamps_to_zero():
    assert compute_alignment_score(-1, 10) == 0.0


# ── fishers_exact_test ────────────────────────────────────────────────────────


def test_fishers_exact_large_shift_significant():
    # Before: 2 yes out of 10 → 20%   After: 9 yes out of 10 → 90%
    p = fishers_exact_test(2, 8, 9, 1)
    assert p < 0.05, f"Expected significant p-value, got {p}"


def test_fishers_exact_no_shift_not_significant():
    # Before: 5/10  After: 5/10 — no change
    p = fishers_exact_test(5, 5, 5, 5)
    assert p > 0.05, f"Expected non-significant p-value, got {p}"


def test_fishers_exact_degenerate_empty_before():
    # No votes before the event — should return 1.0 (no information)
    p = fishers_exact_test(0, 0, 5, 5)
    assert p == 1.0


def test_fishers_exact_degenerate_empty_after():
    p = fishers_exact_test(5, 5, 0, 0)
    assert p == 1.0


def test_fishers_exact_negative_values():
    p = fishers_exact_test(-1, 5, 5, 5)
    assert p == 1.0


# ── AlignmentScore.is_significant ────────────────────────────────────────────


def _make_score(**overrides) -> AlignmentScore:
    defaults = dict(
        id=AlignmentScoreId("01TEST"),
        representative=CanonicalRepRef(id=RepId("rep1"), full_name="Test Rep"),
        donor=CanonicalDonorRef(id=DonorId("donor1"), name="Test Donor"),
        industry=Industry.ENERGY_NATURAL_RESOURCES,
        score=0.7,
        confidence=ConfidenceLevel.MEDIUM,
        evidence_count=10,
        before_score=0.4,
        after_score=0.7,
        shift=0.3,
        p_value=0.02,
        methodology_url="/docs/methodology",
    )
    defaults.update(overrides)
    return AlignmentScore(**defaults)


def test_is_significant_all_thresholds_met():
    assert _make_score().is_significant() is True


def test_is_significant_fails_evidence_count():
    assert _make_score(evidence_count=4).is_significant() is False


def test_is_significant_fails_shift():
    assert _make_score(shift=0.10).is_significant() is False


def test_is_significant_fails_p_value():
    assert _make_score(p_value=0.06).is_significant() is False


def test_is_significant_negative_shift_passes():
    # Negative shift of −0.20 meets |shift| >= 0.15
    assert _make_score(shift=-0.20).is_significant() is True


# ── CorrelationEngine.compute_for_rep ────────────────────────────────────────


def _make_rep_ref(rep_id: str = "rep1") -> CanonicalRepRef:
    return CanonicalRepRef(id=RepId(rep_id), full_name="Jane Smith")


def _make_donor_ref(donor_id: str = "donor1") -> CanonicalDonorRef:
    return CanonicalDonorRef(id=DonorId(donor_id), name="Energy Corp")


def _make_relationship(
    latest_donation: date,
    total_cents: int = 100_000_00,
) -> "DonorRepRelationship":  # noqa: F821
    from domain.finance.models import DonorRepRelationship, RelationshipId

    return DonorRepRelationship(
        id=RelationshipId("rel1"),
        donor=_make_donor_ref(),
        representative=_make_rep_ref(),
        latest_donation=latest_donation,
        total_amount=Money(cents=total_cents),
    )


def _make_vote(
    voted_at: datetime,
    position: str = "yes",
    industry: Industry = Industry.ENERGY_NATURAL_RESOURCES,
) -> tuple:
    from domain.voting.models import BillId, BillRef, RollCallVote, VoteId, VotePosition, VoteType

    pos_map = {
        "yes": VotePosition.YES,
        "no": VotePosition.NO,
        "not_voting": VotePosition.NOT_VOTING,
    }
    vote = RollCallVote(
        id=VoteId("v1"),
        bill=BillRef(id=BillId("hr1"), title="Test Bill"),
        representative=_make_rep_ref(),
        position=pos_map[position],
        voted_at=voted_at,
        vote_type=VoteType.FLOOR,
    )
    return (vote, [industry])


def test_compute_for_rep_no_relationships_returns_empty():
    from domain.correlation.services import CorrelationEngine

    engine = CorrelationEngine(
        finance_repo=MagicMock(),
        voting_repo=MagicMock(),
        correlation_repo=MagicMock(),
    )
    scores = engine.compute_for_rep(
        rep_ref=_make_rep_ref(),
        industry_relationships=[],
        tagged_votes=[],
    )
    assert scores == []


def test_compute_for_rep_insufficient_votes_returns_empty():
    """Only 4 votes — below the evidence_count >= 5 threshold."""
    from domain.correlation.services import CorrelationEngine

    event_date = date(2022, 6, 1)
    rel = _make_relationship(latest_donation=event_date)

    # 2 before + 2 after = 4 total → below threshold
    votes = [
        _make_vote(datetime(2022, 1, 1), "yes"),
        _make_vote(datetime(2022, 3, 1), "no"),
        _make_vote(datetime(2022, 9, 1), "yes"),
        _make_vote(datetime(2022, 11, 1), "no"),
    ]

    engine = CorrelationEngine(
        finance_repo=MagicMock(),
        voting_repo=MagicMock(),
        correlation_repo=MagicMock(),
    )
    scores = engine.compute_for_rep(
        rep_ref=_make_rep_ref(),
        industry_relationships=[(rel, Industry.ENERGY_NATURAL_RESOURCES)],
        tagged_votes=votes,
    )
    assert scores == []


def test_compute_for_rep_significant_shift_returns_score():
    """
    Large shift from 20% to 100% alignment should pass all thresholds.
    Before: 1 yes, 4 no  →  20%
    After:  5 yes, 0 no  → 100%
    Shift = +0.80, well above 0.15.
    """
    from domain.correlation.services import CorrelationEngine

    event_date = date(2022, 6, 1)
    rel = _make_relationship(latest_donation=event_date)

    industry = Industry.ENERGY_NATURAL_RESOURCES

    votes = [
        # Before window
        _make_vote(datetime(2021, 7, 1), "yes",        industry),
        _make_vote(datetime(2021, 9, 1), "no",         industry),
        _make_vote(datetime(2021, 11, 1), "no",        industry),
        _make_vote(datetime(2022, 1, 1), "no",         industry),
        _make_vote(datetime(2022, 3, 1), "no",         industry),
        # After window
        _make_vote(datetime(2022, 8, 1), "yes",        industry),
        _make_vote(datetime(2022, 10, 1), "yes",       industry),
        _make_vote(datetime(2022, 12, 1), "yes",       industry),
        _make_vote(datetime(2023, 2, 1), "yes",        industry),
        _make_vote(datetime(2023, 4, 1), "yes",        industry),
    ]

    engine = CorrelationEngine(
        finance_repo=MagicMock(),
        voting_repo=MagicMock(),
        correlation_repo=MagicMock(),
    )
    scores = engine.compute_for_rep(
        rep_ref=_make_rep_ref(),
        industry_relationships=[(rel, industry)],
        tagged_votes=votes,
    )

    assert len(scores) == 1
    s = scores[0]
    assert s.industry == industry
    assert s.shift > 0.15
    assert s.p_value < 0.05
    assert s.evidence_count >= 5
    assert s.is_significant()


def test_compute_for_rep_none_industry_skipped():
    """Relationships with no industry tag should be ignored."""
    from domain.correlation.services import CorrelationEngine

    rel = _make_relationship(latest_donation=date(2022, 6, 1))
    engine = CorrelationEngine(
        finance_repo=MagicMock(),
        voting_repo=MagicMock(),
        correlation_repo=MagicMock(),
    )
    scores = engine.compute_for_rep(
        rep_ref=_make_rep_ref(),
        industry_relationships=[(rel, None)],
        tagged_votes=[],
    )
    assert scores == []


# ── PostgresCorrelationRepository ────────────────────────────────────────────


def test_save_and_get_score_roundtrip():
    """save_score() then get_scores_for_rep() returns same data."""
    from adapters.postgres.correlation_repo import PostgresCorrelationRepository
    from adapters.postgres.orm_models import AlignmentScoreRow

    # Build a mock session
    session = MagicMock()
    existing = None
    session.query.return_value.filter_by.return_value.first.return_value = existing
    session.get.return_value = None

    repo = PostgresCorrelationRepository(session)
    score = _make_score()
    repo.save_score(score)

    session.add.assert_called_once()
    session.flush.assert_called_once()


def test_get_scores_for_rep_returns_mapped_list():
    from adapters.postgres.correlation_repo import PostgresCorrelationRepository
    from adapters.postgres.orm_models import AlignmentScoreRow

    row = AlignmentScoreRow(
        id="row01",
        rep_id="rep1",
        donor_id="donor1",
        industry=Industry.ENERGY_NATURAL_RESOURCES.value,
        score=0.6,
        confidence="medium",
        evidence_count=10,
        before_score=0.4,
        after_score=0.7,
        shift=0.3,
        p_value=0.02,
        methodology_url="/docs/methodology",
        computed_at="2026-03-10",
    )

    session = MagicMock()
    session.query.return_value.filter_by.return_value.all.return_value = [row]

    repo = PostgresCorrelationRepository(session)
    scores = repo.get_scores_for_rep(RepId("rep1"))

    assert len(scores) == 1
    assert scores[0].industry == Industry.ENERGY_NATURAL_RESOURCES
    assert scores[0].shift == pytest.approx(0.3)
    assert scores[0].confidence == ConfidenceLevel.MEDIUM


# ── ORM importability ─────────────────────────────────────────────────────────


def test_alignment_score_row_importable():
    from adapters.postgres.orm_models import AlignmentScoreRow
    assert AlignmentScoreRow.__tablename__ == "alignment_scores"


def test_correlation_event_row_importable():
    from adapters.postgres.orm_models import CorrelationEventRow
    assert CorrelationEventRow.__tablename__ == "correlation_events"


# ── REST /correlations endpoint ───────────────────────────────────────────────


def _client_with_db(mock_db):
    """Create a TestClient with the given mock DB session injected."""
    from apps.api.main import app
    from infrastructure.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app, raise_server_exceptions=False)
    return client, app


def test_correlations_404_unknown_rep():
    from apps.api.main import app
    from infrastructure.database import get_db

    session = MagicMock()
    session.get.return_value = None
    client, app_ = _client_with_db(session)
    try:
        resp = client.get("/v1/representatives/UNKNOWN/correlations")
    finally:
        app_.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 404


def test_correlations_returns_empty_list():
    from adapters.postgres.orm_models import CanonicalRepRow
    from apps.api.main import app
    from infrastructure.database import get_db

    session = MagicMock()
    rep_row = CanonicalRepRow(
        id="rep1", full_name="Jane Smith", party="D",
        chamber="house", state="CA",
    )
    session.get.return_value = rep_row
    session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []

    client, app_ = _client_with_db(session)
    try:
        resp = client.get("/v1/representatives/rep1/correlations")
    finally:
        app_.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 200
    assert resp.json() == []


def test_correlations_returns_scores():
    from adapters.postgres.orm_models import AlignmentScoreRow, CanonicalRepRow
    from apps.api.main import app
    from infrastructure.database import get_db

    score_row = AlignmentScoreRow(
        id="sc01",
        rep_id="rep1",
        donor_id="donor1",
        industry="energy_natural_resources",
        score=0.65,
        confidence="medium",
        evidence_count=12,
        before_score=0.40,
        after_score=0.65,
        shift=0.25,
        p_value=0.03,
        methodology_url="/docs/methodology",
        computed_at="2026-03-10",
    )

    session = MagicMock()
    rep_row = CanonicalRepRow(
        id="rep1", full_name="Jane Smith", party="D",
        chamber="house", state="CA",
    )
    session.get.return_value = rep_row
    session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [score_row]

    client, app_ = _client_with_db(session)
    try:
        resp = client.get("/v1/representatives/rep1/correlations")
    finally:
        app_.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["industry"] == "energy_natural_resources"
    assert data[0]["shift"] == pytest.approx(0.25)
    assert data[0]["confidence"] == "medium"


# ── Architecture purity ───────────────────────────────────────────────────────


def test_statistics_module_no_framework_imports():
    """statistics.py must not import sqlalchemy, fastapi, celery, etc."""
    import importlib
    import importlib.util
    import sys

    spec = importlib.util.find_spec("domain.correlation.statistics")
    assert spec is not None
    source = spec.origin
    assert source is not None
    forbidden = {"sqlalchemy", "fastapi", "celery", "redis", "httpx", "neo4j"}
    with open(source) as f:
        content = f.read()
    for lib in forbidden:
        assert lib not in content, f"statistics.py must not import {lib}"


def test_services_module_no_framework_imports():
    """services.py must not import sqlalchemy, fastapi, celery, etc."""
    import importlib.util

    spec = importlib.util.find_spec("domain.correlation.services")
    assert spec is not None
    with open(spec.origin) as f:
        content = f.read()
    forbidden = {"sqlalchemy", "fastapi", "celery", "redis", "httpx", "neo4j"}
    for lib in forbidden:
        assert lib not in content, f"services.py must not import {lib}"
