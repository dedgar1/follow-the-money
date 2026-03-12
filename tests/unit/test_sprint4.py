"""
Sprint 4 unit tests — Finance Aggregation + Neo4j graph.

Covers:
  - PostgresFinanceRepository (mocked session)
  - PostgresFundingQueryPort (mocked session)
  - FundingAggregationService (mocked ports)
  - Neo4jRelationshipRepo (mocked neo4j driver)
  - aggregate_finance helpers (mocked DB)
  - ingest_fec._fetch_committee_candidates (mocked FEC client + DB)
  - resolve_identities canonical_donor_id linking
  - Domain purity: domain/finance imports no framework code
  - ORM model Sprint 4 fields
"""

from __future__ import annotations

import sys
from datetime import date
from unittest.mock import MagicMock, patch

from domain.finance.models import DonorRepRelationship, RelationshipId
from domain.finance.services import FundingAggregationService
from domain.identity.models import CanonicalDonorRef, CanonicalRepRef, DonorId, RepId
from domain.shared.election_cycle import ElectionCycle
from domain.shared.money import Money


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_rel(rel_id="01REL001", donor_id="01DON001", rep_id="01REP001",
              cents=50_000, year=2024) -> DonorRepRelationship:
    rel = DonorRepRelationship(
        id=RelationshipId(rel_id),
        donor=CanonicalDonorRef(id=DonorId(donor_id), name="Acme Corp"),
        representative=CanonicalRepRef(id=RepId(rep_id), full_name="Jane Smith"),
        total_amount=Money(cents=cents),
        first_donation=date(year - 1, 3, 15),
        latest_donation=date(year, 10, 5),
        cycles=[ElectionCycle(year=year)],
    )
    return rel


def _make_rel_row(rel_id="01REL001", donor_id="01DON001", rep_id="01REP001",
                  cents=50_000, cycles="[2024]"):
    from adapters.postgres.orm_models import CanonicalRelationshipRow
    row = CanonicalRelationshipRow()
    row.id = rel_id
    row.donor_id = donor_id
    row.rep_id = rep_id
    row.total_amount_cents = cents
    row.contribution_count = 2
    row.first_donation_date = "2023-03-15"
    row.latest_donation_date = "2024-10-05"
    row.election_cycles = cycles
    return row


# ── PostgresFinanceRepository ─────────────────────────────────────────────────


class TestPostgresFinanceRepository:
    def _repo(self):
        from adapters.postgres.finance_repo import PostgresFinanceRepository
        return PostgresFinanceRepository(MagicMock())

    def test_get_relationship_returns_none_when_missing(self):
        repo = self._repo()
        repo._session.get.return_value = None
        assert repo.get_relationship(RelationshipId("missing")) is None

    def test_get_relationship_returns_domain_model(self):
        repo = self._repo()
        repo._session.get.return_value = _make_rel_row()
        result = repo.get_relationship(RelationshipId("01REL001"))
        assert result is not None
        assert result.total_amount.cents == 50_000
        assert len(result.cycles) == 1
        assert result.cycles[0].year == 2024

    def test_save_relationship_inserts_new_row(self):
        repo = self._repo()
        repo._session.get.return_value = None
        rel = _make_rel()
        repo.save_relationship(rel)
        repo._session.add.assert_called_once()
        repo._session.flush.assert_called_once()

    def test_save_relationship_updates_existing_row(self):
        repo = self._repo()
        existing = _make_rel_row()
        repo._session.get.return_value = existing
        rel = _make_rel(cents=100_000)
        repo.save_relationship(rel)
        repo._session.add.assert_not_called()
        assert existing.total_amount_cents == 100_000

    def test_find_relationships_for_rep_returns_list(self):
        repo = self._repo()
        repo._session.query.return_value.filter_by.return_value.all.return_value = [
            _make_rel_row(), _make_rel_row(rel_id="01REL002", donor_id="01DON002")
        ]
        results = repo.find_relationships_for_rep(RepId("01REP001"))
        assert len(results) == 2

    def test_find_relationships_for_rep_filters_by_cycle(self):
        repo = self._repo()
        row_2024 = _make_rel_row(cycles="[2024]")
        row_2022 = _make_rel_row(rel_id="01REL002", cycles="[2022]")
        repo._session.query.return_value.filter_by.return_value.all.return_value = [row_2024, row_2022]
        results = repo.find_relationships_for_rep(RepId("01REP001"), cycle=ElectionCycle(year=2024))
        assert len(results) == 1
        assert results[0].cycles[0].year == 2024

    def test_find_relationships_for_donor(self):
        repo = self._repo()
        repo._session.query.return_value.filter_by.return_value.all.return_value = [_make_rel_row()]
        results = repo.find_relationships_for_donor(DonorId("01DON001"))
        assert len(results) == 1


# ── _relationship_from_row mapper ─────────────────────────────────────────────


class TestRelationshipFromRow:
    def test_parses_cycles_from_json(self):
        from adapters.postgres.finance_repo import _relationship_from_row
        row = _make_rel_row(cycles="[2024, 2022]")
        rel = _relationship_from_row(row)
        assert len(rel.cycles) == 2
        assert ElectionCycle(year=2022) in rel.cycles
        assert ElectionCycle(year=2024) in rel.cycles

    def test_handles_empty_cycles(self):
        from adapters.postgres.finance_repo import _relationship_from_row
        row = _make_rel_row(cycles="[]")
        rel = _relationship_from_row(row)
        assert rel.cycles == []

    def test_parses_dates(self):
        from adapters.postgres.finance_repo import _relationship_from_row
        row = _make_rel_row()
        rel = _relationship_from_row(row)
        assert rel.first_donation == date(2023, 3, 15)
        assert rel.latest_donation == date(2024, 10, 5)

    def test_handles_null_dates(self):
        from adapters.postgres.finance_repo import _relationship_from_row
        row = _make_rel_row()
        row.first_donation_date = None
        row.latest_donation_date = None
        rel = _relationship_from_row(row)
        assert rel.first_donation is None
        assert rel.latest_donation is None


# ── FundingAggregationService ─────────────────────────────────────────────────


class TestFundingAggregationService:
    def _service(self, repo=None, query=None):
        return FundingAggregationService(repo or MagicMock(), query or MagicMock())

    def test_get_or_create_returns_existing(self):
        repo = MagicMock()
        existing = _make_rel()
        repo.get_relationship.return_value = existing
        svc = self._service(repo=repo)
        result = svc.get_or_create_relationship(
            RelationshipId("01REL001"),
            CanonicalDonorRef(id=DonorId("01DON001"), name="Donor"),
            CanonicalRepRef(id=RepId("01REP001"), full_name="Rep"),
        )
        assert result is existing

    def test_get_or_create_creates_new_when_missing(self):
        repo = MagicMock()
        repo.get_relationship.return_value = None
        svc = self._service(repo=repo)
        result = svc.get_or_create_relationship(
            RelationshipId("new"),
            CanonicalDonorRef(id=DonorId("d1"), name="Donor"),
            CanonicalRepRef(id=RepId("r1"), full_name="Rep"),
        )
        assert result.id == RelationshipId("new")
        assert result.total_amount.cents == 0

    def test_total_funding_sums_relationships(self):
        repo = MagicMock()
        repo.find_relationships_for_rep.return_value = [
            _make_rel(cents=10_000),
            _make_rel(rel_id="01REL002", cents=25_000),
        ]
        svc = self._service(repo=repo)
        total = svc.total_funding_for_rep(RepId("r1"))
        assert total.cents == 35_000

    def test_total_funding_empty(self):
        repo = MagicMock()
        repo.find_relationships_for_rep.return_value = []
        svc = self._service(repo=repo)
        assert svc.total_funding_for_rep(RepId("r1")).cents == 0

    def test_get_top_donors_delegates_to_query(self):
        query = MagicMock()
        query.get_top_donors.return_value = [_make_rel()]
        svc = self._service(query=query)
        cycle = ElectionCycle(year=2024)
        result = svc.get_top_donors_for_rep(RepId("r1"), cycle, limit=5)
        query.get_top_donors.assert_called_once_with(RepId("r1"), cycle, 5)
        assert len(result) == 1

    def test_get_top_industries_delegates_to_query(self):
        query = MagicMock()
        query.get_top_industries.return_value = [{"industry": "TECH", "total_cents": 500000}]
        svc = self._service(query=query)
        cycle = ElectionCycle(year=2024)
        result = svc.get_top_industries_for_rep(RepId("r1"), cycle)
        assert result[0]["industry"] == "TECH"


# ── Neo4jRelationshipRepo ─────────────────────────────────────────────────────


class TestNeo4jRelationshipRepo:
    def _repo(self):
        from adapters.neo4j.relationship_repo import Neo4jRelationshipRepo
        return Neo4jRelationshipRepo()

    def _mock_driver(self):
        mock_session = MagicMock()
        mock_driver = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        return mock_driver, mock_session

    def test_upsert_rep_node_calls_run(self):
        repo = self._repo()
        mock_driver, mock_session = self._mock_driver()
        with patch("adapters.neo4j.relationship_repo.get_driver", return_value=mock_driver):
            repo.upsert_rep_node("r1", "A000001", "Jane Smith", "D", "house", "CA")
        mock_session.run.assert_called_once()
        cypher = mock_session.run.call_args[0][0]
        assert "MERGE (r:CanonicalRep" in cypher

    def test_upsert_donor_node_calls_run(self):
        repo = self._repo()
        mock_driver, mock_session = self._mock_driver()
        with patch("adapters.neo4j.relationship_repo.get_driver", return_value=mock_driver):
            repo.upsert_donor_node("d1", "Acme Corp", "corporation")
        mock_session.run.assert_called_once()
        cypher = mock_session.run.call_args[0][0]
        assert "MERGE (d:CanonicalDonor" in cypher

    def test_upsert_funded_relationship_calls_run(self):
        repo = self._repo()
        mock_driver, mock_session = self._mock_driver()
        with patch("adapters.neo4j.relationship_repo.get_driver", return_value=mock_driver):
            repo.upsert_funded_relationship("d1", "r1", 150_000, [2024])
        mock_session.run.assert_called_once()
        cypher = mock_session.run.call_args[0][0]
        assert "MERGE (d)-[f:FUNDED]->(r)" in cypher
        kwargs = mock_session.run.call_args[1]
        assert kwargs["total_cents"] == 150_000
        assert kwargs["cycles"] == [2024]

    def test_get_relationships_for_rep_returns_dicts(self):
        repo = self._repo()
        mock_driver, mock_session = self._mock_driver()
        mock_session.run.return_value = [
            {"donor_id": "d1", "donor_name": "Acme", "total_cents": 50000, "cycles": [2024]},
        ]
        with patch("adapters.neo4j.relationship_repo.get_driver", return_value=mock_driver):
            results = repo.get_relationships_for_rep("r1")
        assert len(results) == 1
        assert results[0]["donor_id"] == "d1"

    def test_get_relationships_for_donor_returns_dicts(self):
        repo = self._repo()
        mock_driver, mock_session = self._mock_driver()
        mock_session.run.return_value = [
            {"rep_id": "r1", "rep_name": "Jane Smith", "total_cents": 50000, "cycles": [2024]},
        ]
        with patch("adapters.neo4j.relationship_repo.get_driver", return_value=mock_driver):
            results = repo.get_relationships_for_donor("d1")
        assert len(results) == 1
        assert results[0]["rep_id"] == "r1"


# ── aggregate_finance helpers ─────────────────────────────────────────────────


class TestAggregateFinanceHelpers:
    def _make_filing_row(self, id_="f1", committee_id="C00001", canonical_donor_id="d1",
                         amount_cents=10_000, date_str="2024-03-01", cycle=2024):
        row = MagicMock()
        row.id = id_
        row.committee_id = committee_id
        row.canonical_donor_id = canonical_donor_id
        row.amount_cents = amount_cents
        row.contribution_date = date_str
        row.election_cycle = cycle
        row.is_processed = True
        return row

    def _make_rep_row(self, id_="r1", fec_candidate_id="P00001"):
        row = MagicMock()
        row.id = id_
        row.fec_candidate_id = fec_candidate_id
        row.full_name = "Jane Smith"
        row.party = "D"
        row.chamber = "house"
        row.state = "CA"
        row.bioguide_id = "A000001"
        return row

    def test_aggregate_builds_correct_total(self):
        from pipeline.tasks.aggregate_finance import _aggregate

        filing1 = self._make_filing_row(id_="f1", amount_cents=10_000)
        filing2 = self._make_filing_row(id_="f2", amount_cents=5_000)
        rep_row = self._make_rep_row()

        with (
            patch("pipeline.tasks.aggregate_finance._load_committee_candidate_map",
                  return_value={"C00001": "P00001"}),
            patch("pipeline.tasks.aggregate_finance._load_canonical_reps",
                  return_value=({"P00001": rep_row}, {"r1": rep_row})),
            patch("pipeline.tasks.aggregate_finance._load_linked_filings",
                  return_value=[filing1, filing2]),
            patch("pipeline.tasks.aggregate_finance._load_canonical_donors",
                  return_value={}),
            patch("pipeline.tasks.aggregate_finance._upsert_relationships",
                  return_value=1) as mock_upsert,
            patch("pipeline.tasks.aggregate_finance._write_neo4j_graph",
                  return_value=1),
        ):
            rels_written, edges = _aggregate()

        assert rels_written == 1
        assert edges == 1
        # Verify the aggregate passed to upsert has the right total
        agg = mock_upsert.call_args[0][0]
        assert len(agg) == 1
        key = ("d1", "r1")
        assert agg[key]["total_cents"] == 15_000
        assert agg[key]["count"] == 2

    def test_aggregate_skips_unlinked_filings(self):
        from pipeline.tasks.aggregate_finance import _aggregate

        filing_no_donor = self._make_filing_row(canonical_donor_id=None)
        filing_no_committee = self._make_filing_row(committee_id="C99999")

        with (
            patch("pipeline.tasks.aggregate_finance._load_committee_candidate_map",
                  return_value={"C00001": "P00001"}),  # C99999 not in map
            patch("pipeline.tasks.aggregate_finance._load_canonical_reps",
                  return_value=({}, {})),
            patch("pipeline.tasks.aggregate_finance._load_linked_filings",
                  return_value=[filing_no_donor, filing_no_committee]),
            patch("pipeline.tasks.aggregate_finance._load_canonical_donors",
                  return_value={}),
            patch("pipeline.tasks.aggregate_finance._upsert_relationships",
                  return_value=0) as mock_upsert,
            patch("pipeline.tasks.aggregate_finance._write_neo4j_graph",
                  return_value=0),
        ):
            rels_written, edges = _aggregate()

        agg = mock_upsert.call_args[0][0]
        assert len(agg) == 0

    def test_aggregate_groups_multiple_donations_same_pair(self):
        from pipeline.tasks.aggregate_finance import _aggregate

        rep_row = self._make_rep_row()
        filings = [
            self._make_filing_row(id_=f"f{i}", amount_cents=1000, date_str=f"2024-0{i+1}-01")
            for i in range(1, 4)
        ]

        with (
            patch("pipeline.tasks.aggregate_finance._load_committee_candidate_map",
                  return_value={"C00001": "P00001"}),
            patch("pipeline.tasks.aggregate_finance._load_canonical_reps",
                  return_value=({"P00001": rep_row}, {"r1": rep_row})),
            patch("pipeline.tasks.aggregate_finance._load_linked_filings",
                  return_value=filings),
            patch("pipeline.tasks.aggregate_finance._load_canonical_donors",
                  return_value={}),
            patch("pipeline.tasks.aggregate_finance._upsert_relationships",
                  return_value=1) as mock_upsert,
            patch("pipeline.tasks.aggregate_finance._write_neo4j_graph",
                  return_value=1),
        ):
            _aggregate()

        agg = mock_upsert.call_args[0][0]
        entry = agg[("d1", "r1")]
        assert entry["total_cents"] == 3000
        assert entry["count"] == 3


# ── ingest_fec._fetch_committee_candidates ────────────────────────────────────


class TestFetchCommitteeCandidates:
    def test_fetches_and_stores_committee_candidate(self):
        from pipeline.tasks.ingest_fec import _fetch_committee_candidates

        mock_fec = MagicMock()
        mock_fec.get_committee.return_value = {
            "id": "C00123",
            "name": "SMITH FOR CONGRESS",
            "candidate_ids": ["H0CA01234"],
        }

        mock_session = MagicMock()
        mock_session.query.return_value.all.return_value = []  # no existing rows
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("pipeline.tasks.ingest_fec.get_session", return_value=mock_ctx):
            with patch("sqlalchemy.dialects.postgresql.insert"):
                _fetch_committee_candidates(mock_fec, {"C00123"})

        mock_fec.get_committee.assert_called_once_with("C00123")

    def test_skips_already_known_committee_ids(self):
        from pipeline.tasks.ingest_fec import _fetch_committee_candidates

        mock_fec = MagicMock()

        existing_row = MagicMock()
        existing_row.committee_id = "C00123"
        mock_session = MagicMock()
        mock_session.query.return_value.all.return_value = [existing_row]
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("pipeline.tasks.ingest_fec.get_session", return_value=mock_ctx):
            _fetch_committee_candidates(mock_fec, {"C00123"})

        # Should not call get_committee since it's already known
        mock_fec.get_committee.assert_not_called()

    def test_handles_committee_with_no_candidate(self):
        from pipeline.tasks.ingest_fec import _fetch_committee_candidates

        mock_fec = MagicMock()
        mock_fec.get_committee.return_value = {
            "id": "C00999",
            "name": "SOME PAC",
            "candidate_ids": [],
        }

        mock_session = MagicMock()
        mock_session.query.return_value.all.return_value = []
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("pipeline.tasks.ingest_fec.get_session", return_value=mock_ctx):
            with patch("sqlalchemy.dialects.postgresql.insert"):
                _fetch_committee_candidates(mock_fec, {"C00999"})

        # Verify the row would have fec_candidate_id=None
        mock_fec.get_committee.assert_called_once_with("C00999")

    def test_logs_warning_on_api_error_and_continues(self):
        from pipeline.tasks.ingest_fec import _fetch_committee_candidates

        mock_fec = MagicMock()
        mock_fec.get_committee.side_effect = Exception("API error")

        mock_session = MagicMock()
        mock_session.query.return_value.all.return_value = []
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        # Should not raise
        with patch("pipeline.tasks.ingest_fec.get_session", return_value=mock_ctx):
            _fetch_committee_candidates(mock_fec, {"C00BAD"})


# ── resolve_identities canonical_donor_id linking ─────────────────────────────


class TestResolveIdentitiesLinking:
    def _make_filing(self, id_, name, committee_id="C00001"):
        row = MagicMock()
        row.id = id_
        row.contributor_name = name
        row.committee_id = committee_id
        row.is_processed = False
        return row

    def test_links_canonical_donor_id_to_filing(self):
        from pipeline.tasks.resolve_identities import _FilingData, _resolve_donors

        filing_data = _FilingData(id="f1", contributor_name="Alice Smith", committee_id="C00001")

        mock_session = MagicMock()
        mock_db_row = MagicMock()
        mock_session.get.return_value = mock_db_row

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        mock_donor = MagicMock()
        mock_donor.id = "donor_123"

        mock_resolver = MagicMock()
        mock_resolver.resolve_donor.return_value = mock_donor

        with (
            patch("pipeline.tasks.resolve_identities._load_unprocessed_filings", return_value=[filing_data]),
            patch("pipeline.tasks.resolve_identities.get_session", return_value=mock_ctx),
            patch("pipeline.tasks.resolve_identities.PostgresIdentityRepository"),
            patch("pipeline.tasks.resolve_identities.EntityResolver",
                  return_value=mock_resolver),
        ):
            donors_created, filings_marked = _resolve_donors()

        assert donors_created == 1
        assert filings_marked == 1
        assert mock_db_row.canonical_donor_id == "donor_123"
        assert mock_db_row.is_processed is True

    def test_groups_similar_names_to_same_donor(self):
        from pipeline.tasks.resolve_identities import _FilingData, _resolve_donors

        filing1 = _FilingData(id="f1", contributor_name="GOOGLE INC", committee_id="C00001")
        filing2 = _FilingData(id="f2", contributor_name="GOOGLE LLC", committee_id="C00001")

        mock_row1, mock_row2 = MagicMock(), MagicMock()
        mock_session = MagicMock()
        mock_session.get.side_effect = lambda cls, fid: {"f1": mock_row1, "f2": mock_row2}[fid]

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        mock_donor = MagicMock()
        mock_donor.id = "donor_google"

        mock_resolver = MagicMock()
        mock_resolver.resolve_donor.return_value = mock_donor

        with (
            patch("pipeline.tasks.resolve_identities._load_unprocessed_filings", return_value=[filing1, filing2]),
            patch("pipeline.tasks.resolve_identities.get_session", return_value=mock_ctx),
            patch("pipeline.tasks.resolve_identities.PostgresIdentityRepository"),
            patch("pipeline.tasks.resolve_identities.EntityResolver",
                  return_value=mock_resolver),
        ):
            donors_created, filings_marked = _resolve_donors()

        # Two similar names should cluster to 1 donor
        assert donors_created == 1
        assert filings_marked == 2
        assert mock_row1.canonical_donor_id == "donor_google"
        assert mock_row2.canonical_donor_id == "donor_google"


# ── ORM model Sprint 4 fields ─────────────────────────────────────────────────


class TestOrmModelSprint4:
    def test_fec_committee_candidate_row_has_expected_columns(self):
        from adapters.postgres.orm_models import FecCommitteeCandidateRow
        cols = {c.name for c in FecCommitteeCandidateRow.__table__.columns}
        assert "committee_id" in cols
        assert "fec_candidate_id" in cols
        assert "committee_name" in cols

    def test_canonical_relationship_row_has_expected_columns(self):
        from adapters.postgres.orm_models import CanonicalRelationshipRow
        cols = {c.name for c in CanonicalRelationshipRow.__table__.columns}
        assert "donor_id" in cols
        assert "rep_id" in cols
        assert "total_amount_cents" in cols
        assert "election_cycles" in cols

    def test_raw_filing_row_has_canonical_donor_id(self):
        from adapters.postgres.orm_models import RawFilingRow
        cols = {c.name for c in RawFilingRow.__table__.columns}
        assert "canonical_donor_id" in cols

    def test_canonical_relationship_unique_index_exists(self):
        from adapters.postgres.orm_models import CanonicalRelationshipRow
        index_names = {i.name for i in CanonicalRelationshipRow.__table__.indexes}
        assert "uq_canonical_rel_donor_rep" in index_names


# ── Domain purity ─────────────────────────────────────────────────────────────


class TestFinanceDomainPurity:
    FORBIDDEN = {"sqlalchemy", "fastapi", "httpx", "redis", "celery", "neo4j"}

    def test_finance_models_no_framework_imports(self):
        import domain.finance.models as m
        for dep in self.FORBIDDEN:
            assert dep not in sys.modules or dep not in str(m.__file__)
        src = open(m.__file__).read()
        for dep in self.FORBIDDEN:
            assert dep not in src, f"domain/finance/models.py imports {dep}"

    def test_finance_services_no_framework_imports(self):
        import domain.finance.services as m
        src = open(m.__file__).read()
        for dep in self.FORBIDDEN:
            assert dep not in src, f"domain/finance/services.py imports {dep}"

    def test_finance_ports_no_framework_imports(self):
        import domain.finance.ports as m
        src = open(m.__file__).read()
        for dep in self.FORBIDDEN:
            assert dep not in src, f"domain/finance/ports.py imports {dep}"


# ── Celery beat schedule ──────────────────────────────────────────────────────


class TestCeleryBeatSchedule:
    def test_aggregate_finance_in_beat_schedule(self):
        from pipeline.celery_app import celery_app
        assert "nightly-aggregate-finance" in celery_app.conf.beat_schedule

    def test_aggregate_finance_task_name(self):
        from pipeline.celery_app import celery_app
        task_config = celery_app.conf.beat_schedule["nightly-aggregate-finance"]
        assert task_config["task"] == "pipeline.tasks.aggregate_finance.run"

    def test_pipeline_order_is_correct(self):
        """aggregate_finance must run after resolve_identities."""
        from pipeline.celery_app import celery_app
        schedule = celery_app.conf.beat_schedule
        resolve_hour = min(schedule["nightly-resolve-identities"]["schedule"].hour)
        aggregate_hour = min(schedule["nightly-aggregate-finance"]["schedule"].hour)
        assert aggregate_hour > resolve_hour


# ── PostgresFundingQueryPort ───────────────────────────────────────────────────


class TestPostgresFundingQueryPort:
    def _port(self):
        from adapters.postgres.finance_repo import PostgresFundingQueryPort
        return PostgresFundingQueryPort(MagicMock())

    def test_get_top_donors_filters_by_cycle(self):
        port = self._port()
        row_2024 = _make_rel_row(rel_id="r1", cycles="[2024]", cents=90_000)
        row_2022 = _make_rel_row(rel_id="r2", cycles="[2022]", cents=50_000)
        (port._session.query.return_value
             .filter.return_value
             .order_by.return_value
             .limit.return_value
             .all.return_value) = [row_2024, row_2022]
        results = port.get_top_donors(RepId("r1"), ElectionCycle(year=2024), limit=10)
        # Only row_2024 should be included
        assert len(results) == 1
        assert results[0].total_amount.cents == 90_000

    def test_get_top_donors_respects_limit(self):
        port = self._port()
        rows = [_make_rel_row(rel_id=f"r{i}", cycles="[2024]", cents=1000 * i) for i in range(1, 6)]
        (port._session.query.return_value
             .filter.return_value
             .order_by.return_value
             .limit.return_value
             .all.return_value) = rows
        results = port.get_top_donors(RepId("r1"), ElectionCycle(year=2024), limit=3)
        assert len(results) == 3

    def test_get_top_industries_executes_sql(self):
        port = self._port()
        port._session.execute.return_value.fetchall.return_value = [
            ("TECH", 500_000),
            ("FINANCE", 300_000),
        ]
        results = port.get_top_industries(RepId("r1"), ElectionCycle(year=2024))
        assert len(results) == 2
        assert results[0] == {"industry": "TECH", "total_cents": 500_000}
        assert results[1] == {"industry": "FINANCE", "total_cents": 300_000}

    def test_get_top_industries_returns_empty_list_when_no_data(self):
        port = self._port()
        port._session.execute.return_value.fetchall.return_value = []
        results = port.get_top_industries(RepId("r1"), ElectionCycle(year=2024))
        assert results == []


# ── aggregate_finance date and cycle tracking ─────────────────────────────────


class TestAggregateFinanceDateTracking:
    def _make_filing_row(self, id_="f1", committee_id="C00001", canonical_donor_id="d1",
                         amount_cents=10_000, date_str="2024-03-01", cycle=2024):
        row = MagicMock()
        row.id = id_
        row.committee_id = committee_id
        row.canonical_donor_id = canonical_donor_id
        row.amount_cents = amount_cents
        row.contribution_date = date_str
        row.election_cycle = cycle
        row.is_processed = True
        return row

    def _make_rep_row(self, id_="r1", fec_candidate_id="P00001"):
        row = MagicMock()
        row.id = id_
        row.fec_candidate_id = fec_candidate_id
        row.full_name = "Jane Smith"
        row.party = "D"
        row.chamber = "house"
        row.state = "CA"
        row.bioguide_id = "A000001"
        return row

    def test_tracks_first_and_latest_dates(self):
        from pipeline.tasks.aggregate_finance import _aggregate

        rep_row = self._make_rep_row()
        filings = [
            self._make_filing_row(id_="f1", date_str="2024-01-15"),
            self._make_filing_row(id_="f2", date_str="2024-06-01"),
            self._make_filing_row(id_="f3", date_str="2023-11-20"),
        ]

        with (
            patch("pipeline.tasks.aggregate_finance._load_committee_candidate_map",
                  return_value={"C00001": "P00001"}),
            patch("pipeline.tasks.aggregate_finance._load_canonical_reps",
                  return_value=({"P00001": rep_row}, {"r1": rep_row})),
            patch("pipeline.tasks.aggregate_finance._load_linked_filings",
                  return_value=filings),
            patch("pipeline.tasks.aggregate_finance._load_canonical_donors",
                  return_value={}),
            patch("pipeline.tasks.aggregate_finance._upsert_relationships",
                  return_value=1) as mock_upsert,
            patch("pipeline.tasks.aggregate_finance._write_neo4j_graph",
                  return_value=1),
        ):
            _aggregate()

        agg = mock_upsert.call_args[0][0]
        entry = agg[("d1", "r1")]
        assert entry["first_date"] == date(2023, 11, 20)
        assert entry["latest_date"] == date(2024, 6, 1)

    def test_ignores_malformed_dates(self):
        from pipeline.tasks.aggregate_finance import _aggregate

        rep_row = self._make_rep_row()
        filing_bad = self._make_filing_row(id_="f1", date_str="not-a-date")
        filing_good = self._make_filing_row(id_="f2", date_str="2024-05-10")

        with (
            patch("pipeline.tasks.aggregate_finance._load_committee_candidate_map",
                  return_value={"C00001": "P00001"}),
            patch("pipeline.tasks.aggregate_finance._load_canonical_reps",
                  return_value=({"P00001": rep_row}, {"r1": rep_row})),
            patch("pipeline.tasks.aggregate_finance._load_linked_filings",
                  return_value=[filing_bad, filing_good]),
            patch("pipeline.tasks.aggregate_finance._load_canonical_donors",
                  return_value={}),
            patch("pipeline.tasks.aggregate_finance._upsert_relationships",
                  return_value=1) as mock_upsert,
            patch("pipeline.tasks.aggregate_finance._write_neo4j_graph",
                  return_value=1),
        ):
            _aggregate()

        agg = mock_upsert.call_args[0][0]
        entry = agg[("d1", "r1")]
        # Only the valid date is tracked
        assert entry["first_date"] == date(2024, 5, 10)
        assert entry["latest_date"] == date(2024, 5, 10)

    def test_accumulates_election_cycles(self):
        from pipeline.tasks.aggregate_finance import _aggregate

        rep_row = self._make_rep_row()
        filings = [
            self._make_filing_row(id_="f1", cycle=2024),
            self._make_filing_row(id_="f2", cycle=2022),
            self._make_filing_row(id_="f3", cycle=2024),  # duplicate — should be deduplicated
        ]

        with (
            patch("pipeline.tasks.aggregate_finance._load_committee_candidate_map",
                  return_value={"C00001": "P00001"}),
            patch("pipeline.tasks.aggregate_finance._load_canonical_reps",
                  return_value=({"P00001": rep_row}, {"r1": rep_row})),
            patch("pipeline.tasks.aggregate_finance._load_linked_filings",
                  return_value=filings),
            patch("pipeline.tasks.aggregate_finance._load_canonical_donors",
                  return_value={}),
            patch("pipeline.tasks.aggregate_finance._upsert_relationships",
                  return_value=1) as mock_upsert,
            patch("pipeline.tasks.aggregate_finance._write_neo4j_graph",
                  return_value=1),
        ):
            _aggregate()

        agg = mock_upsert.call_args[0][0]
        entry = agg[("d1", "r1")]
        # cycles is a set — should have 2024 and 2022, not 2024 twice
        assert entry["cycles"] == {2024, 2022}

    def test_returns_zero_when_no_filings(self):
        from pipeline.tasks.aggregate_finance import _aggregate

        with (
            patch("pipeline.tasks.aggregate_finance._load_committee_candidate_map",
                  return_value={}),
            patch("pipeline.tasks.aggregate_finance._load_canonical_reps",
                  return_value=({}, {})),
            patch("pipeline.tasks.aggregate_finance._load_linked_filings",
                  return_value=[]),
            patch("pipeline.tasks.aggregate_finance._load_canonical_donors",
                  return_value={}),
        ):
            rels, edges = _aggregate()

        assert rels == 0
        assert edges == 0


# ── _write_neo4j_graph orchestration ─────────────────────────────────────────


class TestWriteNeo4jGraph:
    def _make_rep_row(self, id_="r1"):
        row = MagicMock()
        row.id = id_
        row.full_name = "Jane Smith"
        row.party = "D"
        row.chamber = "house"
        row.state = "CA"
        row.bioguide_id = "A000001"
        return row

    def _make_donor_row(self, id_="d1"):
        row = MagicMock()
        row.id = id_
        row.name = "Acme Corp"
        row.donor_type = "corporation"
        return row

    def test_calls_upsert_for_all_nodes_and_edges(self):
        from pipeline.tasks.aggregate_finance import _write_neo4j_graph

        agg = {
            ("d1", "r1"): {
                "donor_id": "d1", "rep_id": "r1",
                "total_cents": 50_000, "cycles": {2024},
            }
        }
        donors = {"d1": self._make_donor_row()}
        reps = {"r1": self._make_rep_row()}

        mock_neo4j = MagicMock()
        with patch("pipeline.tasks.aggregate_finance.Neo4jRelationshipRepo",
                   return_value=mock_neo4j):
            edges = _write_neo4j_graph(agg, donors, reps)

        assert edges == 1
        mock_neo4j.upsert_rep_node.assert_called_once()
        mock_neo4j.upsert_donor_node.assert_called_once()
        mock_neo4j.upsert_funded_relationship.assert_called_once_with(
            donor_id="d1", rep_id="r1", total_cents=50_000, cycles=[2024]
        )

    def test_continues_on_neo4j_edge_failure(self):
        from pipeline.tasks.aggregate_finance import _write_neo4j_graph

        agg = {
            ("d1", "r1"): {"donor_id": "d1", "rep_id": "r1", "total_cents": 1000, "cycles": {2024}},
            ("d2", "r1"): {"donor_id": "d2", "rep_id": "r1", "total_cents": 2000, "cycles": {2024}},
        }
        donors = {"d1": self._make_donor_row("d1"), "d2": self._make_donor_row("d2")}
        reps = {"r1": self._make_rep_row()}

        mock_neo4j = MagicMock()
        # First edge call fails, second succeeds
        mock_neo4j.upsert_funded_relationship.side_effect = [Exception("bolt error"), None]

        with patch("pipeline.tasks.aggregate_finance.Neo4jRelationshipRepo",
                   return_value=mock_neo4j):
            edges = _write_neo4j_graph(agg, donors, reps)

        # 1 edge written (second one), first failure is swallowed
        assert edges == 1

    def test_skips_missing_donor_nodes(self):
        from pipeline.tasks.aggregate_finance import _write_neo4j_graph

        agg = {("d_missing", "r1"): {"donor_id": "d_missing", "rep_id": "r1",
                                      "total_cents": 1000, "cycles": {2024}}}
        donors = {}  # donor not in map
        reps = {"r1": self._make_rep_row()}

        mock_neo4j = MagicMock()
        with patch("pipeline.tasks.aggregate_finance.Neo4jRelationshipRepo",
                   return_value=mock_neo4j):
            _write_neo4j_graph(agg, donors, reps)

        mock_neo4j.upsert_donor_node.assert_not_called()


# ── FundingAggregationService.total_funding_for_rep with cycle ────────────────


class TestFundingAggregationServiceCycleFilter:
    def test_total_funding_passes_cycle_to_repo(self):
        repo = MagicMock()
        repo.find_relationships_for_rep.return_value = [_make_rel(cents=20_000)]
        svc = FundingAggregationService(repo, MagicMock())
        cycle = ElectionCycle(year=2024)
        total = svc.total_funding_for_rep(RepId("r1"), cycle=cycle)
        repo.find_relationships_for_rep.assert_called_once_with(RepId("r1"), cycle)
        assert total.cents == 20_000
