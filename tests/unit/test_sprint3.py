"""
Sprint 3 unit tests — rapidfuzz entity resolver, domain identity service,
Postgres identity repo (mocked session), and resolve_identities task helpers.
"""

from __future__ import annotations

from unittest.mock import MagicMock


# ── Text normalisation ────────────────────────────────────────────────────────


class TestNormalise:
    def test_uppercase(self):
        from adapters.nlp.entity_resolver import normalise
        assert normalise("google inc") == "GOOGLE"

    def test_strips_legal_suffixes(self):
        from adapters.nlp.entity_resolver import normalise
        assert normalise("Acme Corp") == "ACME"
        assert normalise("Smith LLC") == "SMITH"
        assert normalise("Jones LLP") == "JONES"

    def test_strips_punctuation(self):
        from adapters.nlp.entity_resolver import normalise
        assert normalise("Smith, John") == "SMITH JOHN"

    def test_collapses_whitespace(self):
        from adapters.nlp.entity_resolver import normalise
        assert normalise("  JOHN   SMITH  ") == "JOHN SMITH"

    def test_empty_string(self):
        from adapters.nlp.entity_resolver import normalise
        assert normalise("") == ""


# ── DonorNameResolver ─────────────────────────────────────────────────────────


class TestDonorNameResolver:
    def test_same_name_forms_one_cluster(self):
        from adapters.nlp.entity_resolver import DonorNameResolver
        r = DonorNameResolver()
        r.add("GOOGLE INC", "C001")
        r.add("GOOGLE LLC", "C002")
        r.add("Google, Inc.", "C003")
        assert len(r.clusters) == 1
        assert sorted(r.clusters[0].fec_ids) == ["C001", "C002", "C003"]

    def test_different_names_form_separate_clusters(self):
        from adapters.nlp.entity_resolver import DonorNameResolver
        r = DonorNameResolver()
        r.add("GOOGLE INC", "C001")
        r.add("MICROSOFT CORP", "C002")
        assert len(r.clusters) == 2

    def test_canonical_name_is_normalised_first_seen(self):
        from adapters.nlp.entity_resolver import DonorNameResolver
        r = DonorNameResolver()
        r.add("JOHN SMITH", "C001")
        r.add("John Smith", "C002")
        assert len(r.clusters) == 1
        assert r.clusters[0].canonical_name == "JOHN SMITH"

    def test_fec_id_not_duplicated(self):
        from adapters.nlp.entity_resolver import DonorNameResolver
        r = DonorNameResolver()
        r.add("ACME INC", "C001")
        r.add("ACME INC", "C001")  # same name, same FEC ID
        assert len(r.clusters) == 1
        assert r.clusters[0].fec_ids.count("C001") == 1

    def test_batch_add(self):
        from adapters.nlp.entity_resolver import DonorNameResolver
        r = DonorNameResolver()
        r.batch_add([("GOOGLE INC", "C001"), ("GOOGLE LLC", "C002"), ("APPLE INC", "C003")])
        assert len(r.clusters) == 2

    def test_empty_name_handled(self):
        from adapters.nlp.entity_resolver import DonorNameResolver
        r = DonorNameResolver()
        r.add("", "C001")
        assert len(r.clusters) == 1

    def test_high_threshold_keeps_variants_separate(self):
        from adapters.nlp.entity_resolver import DonorNameResolver
        r = DonorNameResolver(threshold=99)  # near-exact only
        r.add("JOHN SMITH", "C001")
        r.add("JOHN SMITHE", "C002")   # clearly different
        assert len(r.clusters) == 2


# ── RepNameResolver ───────────────────────────────────────────────────────────


class TestRepNameResolver:
    def test_resolves_known_rep(self):
        from adapters.nlp.entity_resolver import RepNameResolver
        r = RepNameResolver()
        r.index_known_reps([("A000370", "Alma Adams"), ("P000197", "Nancy Pelosi")])
        assert r.resolve("ALMA ADAMS") == "A000370"

    def test_resolves_with_name_variations(self):
        from adapters.nlp.entity_resolver import RepNameResolver
        r = RepNameResolver()
        r.index_known_reps([("A000370", "Alma Adams")])
        assert r.resolve("ADAMS, ALMA") == "A000370"

    def test_returns_none_for_unknown(self):
        from adapters.nlp.entity_resolver import RepNameResolver
        r = RepNameResolver()
        r.index_known_reps([("A000370", "Alma Adams")])
        assert r.resolve("COMPLETELY DIFFERENT PERSON") is None

    def test_returns_none_when_no_index(self):
        from adapters.nlp.entity_resolver import RepNameResolver
        r = RepNameResolver()
        assert r.resolve("JOHN SMITH") is None


# ── Domain identity service ───────────────────────────────────────────────────


class TestEntityResolverService:
    def _make_repo(self):
        repo = MagicMock()
        repo.find_rep_by_bioguide_id.return_value = None
        repo.find_donor_by_fec_id.return_value = None
        return repo

    def test_resolve_rep_creates_new(self):
        from domain.identity.models import Chamber, Party
        from domain.identity.services import EntityResolver
        repo = self._make_repo()
        service = EntityResolver(repo)
        rep = service.resolve_rep_from_bioguide(
            bioguide_id="A000370",
            full_name="Alma Adams",
            party="D",
            chamber="House",
            state="NC",
        )
        assert rep.bioguide_id == "A000370"
        assert rep.party == Party.DEMOCRAT
        assert rep.chamber == Chamber.HOUSE
        assert rep.state == "NC"
        repo.save_rep.assert_called_once()

    def test_resolve_rep_returns_existing(self):
        from domain.identity.services import EntityResolver

        existing = MagicMock()
        repo = self._make_repo()
        repo.find_rep_by_bioguide_id.return_value = existing
        service = EntityResolver(repo)
        result = service.resolve_rep_from_bioguide(
            bioguide_id="A000370", full_name="Alma Adams",
            party="D", chamber="House", state="NC",
        )
        assert result is existing
        repo.save_rep.assert_not_called()

    def test_resolve_donor_creates_new(self):
        from domain.identity.models import DonorType
        from domain.identity.services import EntityResolver
        repo = self._make_repo()
        service = EntityResolver(repo)
        donor = service.resolve_donor(
            canonical_name="GOOGLE",
            donor_type="pac",
            fec_id="C001",
            state="CA",
        )
        assert donor.name == "GOOGLE"
        assert donor.donor_type == DonorType.PAC
        assert "C001" in donor.fec_ids
        repo.save_donor.assert_called_once()

    def test_merge_donor_fec_id(self):
        from domain.identity.services import EntityResolver

        repo = self._make_repo()
        service = EntityResolver(repo)

        donor = MagicMock()
        donor.fec_ids = ["C001"]
        service.merge_donor_fec_id(donor, "C002")
        assert "C002" in donor.fec_ids
        repo.save_donor.assert_called_once()

    def test_merge_donor_fec_id_no_duplicate(self):
        from domain.identity.services import EntityResolver
        repo = self._make_repo()
        service = EntityResolver(repo)
        donor = MagicMock()
        donor.fec_ids = ["C001"]
        service.merge_donor_fec_id(donor, "C001")
        repo.save_donor.assert_not_called()

    def test_party_parsing(self):
        from domain.identity.models import Party
        from domain.identity.services import _parse_party
        assert _parse_party("D") == Party.DEMOCRAT
        assert _parse_party("R") == Party.REPUBLICAN
        assert _parse_party("I") == Party.INDEPENDENT
        assert _parse_party("X") == Party.OTHER

    def test_chamber_parsing(self):
        from domain.identity.models import Chamber
        from domain.identity.services import _parse_chamber
        assert _parse_chamber("House") == Chamber.HOUSE
        assert _parse_chamber("house") == Chamber.HOUSE
        assert _parse_chamber("Senate") == Chamber.SENATE
        assert _parse_chamber("senate") == Chamber.SENATE


# ── Architecture: domain/identity must not import frameworks ──────────────────


class TestIdentityDomainPurity:
    FORBIDDEN = ["sqlalchemy", "httpx", "fastapi", "celery", "redis"]

    def test_identity_services_no_framework_imports(self):
        import ast
        import pathlib
        src = pathlib.Path("domain/identity/services.py").read_text()
        tree = ast.parse(src)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.append(node.names[0].name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".")[0])
        for forbidden in self.FORBIDDEN:
            assert forbidden not in " ".join(imports), \
                f"domain/identity/services.py must not import {forbidden}"


# ── PostgresIdentityRepository ────────────────────────────────────────────────


def _make_session():
    """Return a MagicMock that behaves like a SQLAlchemy Session."""
    session = MagicMock()
    session.get.return_value = None  # default: nothing in DB
    session.query.return_value.filter_by.return_value.first.return_value = None
    session.query.return_value.all.return_value = []
    return session


def _canonical_rep_row(bioguide_id="A000370"):
    from adapters.postgres.orm_models import CanonicalRepRow
    row = MagicMock(spec=CanonicalRepRow)
    row.id = "01TEST"
    row.full_name = "Alma Adams"
    row.party = "D"
    row.chamber = "house"
    row.state = "NC"
    row.district = "NC-12"
    row.bioguide_id = bioguide_id
    row.fec_candidate_id = None
    return row


def _canonical_donor_row(fec_ids='["C001"]'):
    from adapters.postgres.orm_models import CanonicalDonorRow
    row = MagicMock(spec=CanonicalDonorRow)
    row.id = "01DONOR"
    row.name = "GOOGLE"
    row.donor_type = "pac"
    row.industry = None
    row.state = "CA"
    row.fec_ids = fec_ids
    return row


class TestPostgresIdentityRepository:
    def test_get_rep_returns_none_when_missing(self):
        from adapters.postgres.identity_repo import PostgresIdentityRepository
        from domain.identity.models import RepId
        session = _make_session()
        repo = PostgresIdentityRepository(session)
        assert repo.get_rep(RepId("nonexistent")) is None

    def test_get_rep_maps_row_to_domain(self):
        from adapters.postgres.identity_repo import PostgresIdentityRepository
        from domain.identity.models import Chamber, Party, RepId
        session = _make_session()
        session.get.return_value = _canonical_rep_row()
        repo = PostgresIdentityRepository(session)
        rep = repo.get_rep(RepId("01TEST"))
        assert rep is not None
        assert rep.bioguide_id == "A000370"
        assert rep.party == Party.DEMOCRAT
        assert rep.chamber == Chamber.HOUSE

    def test_save_rep_adds_new_row(self):
        from adapters.postgres.identity_repo import PostgresIdentityRepository
        from domain.identity.models import Chamber, CanonicalRep, Party, RepId
        session = _make_session()
        session.get.return_value = None  # no existing row
        repo = PostgresIdentityRepository(session)
        rep = CanonicalRep(
            id=RepId("01TEST"),
            full_name="Alma Adams",
            party=Party.DEMOCRAT,
            chamber=Chamber.HOUSE,
            state="NC",
            district="NC-12",
            bioguide_id="A000370",
            fec_candidate_id=None,
        )
        repo.save_rep(rep)
        session.add.assert_called_once()
        session.flush.assert_called_once()

    def test_save_rep_updates_existing_row(self):
        from adapters.postgres.identity_repo import PostgresIdentityRepository
        from domain.identity.models import Chamber, CanonicalRep, Party, RepId
        session = _make_session()
        existing_row = _canonical_rep_row()
        session.get.return_value = existing_row
        repo = PostgresIdentityRepository(session)
        rep = CanonicalRep(
            id=RepId("01TEST"),
            full_name="Alma S. Adams",  # updated name
            party=Party.DEMOCRAT,
            chamber=Chamber.HOUSE,
            state="NC",
            district="NC-12",
            bioguide_id="A000370",
            fec_candidate_id=None,
        )
        repo.save_rep(rep)
        assert existing_row.full_name == "Alma S. Adams"
        session.add.assert_not_called()  # update, not insert

    def test_find_rep_by_bioguide_id_found(self):
        from adapters.postgres.identity_repo import PostgresIdentityRepository
        session = _make_session()
        session.query.return_value.filter_by.return_value.first.return_value = _canonical_rep_row()
        repo = PostgresIdentityRepository(session)
        rep = repo.find_rep_by_bioguide_id("A000370")
        assert rep is not None
        assert rep.bioguide_id == "A000370"

    def test_find_rep_by_bioguide_id_not_found(self):
        from adapters.postgres.identity_repo import PostgresIdentityRepository
        session = _make_session()
        repo = PostgresIdentityRepository(session)
        assert repo.find_rep_by_bioguide_id("UNKNOWN") is None

    def test_find_rep_by_lis_id_resolves_via_mapping(self):
        from adapters.postgres.identity_repo import PostgresIdentityRepository
        from adapters.postgres.orm_models import LisBioguideMapRow
        session = _make_session()
        mapping = MagicMock(spec=LisBioguideMapRow)
        mapping.bioguide_id = "A000370"
        # session.get: first call (LisBioguideMapRow) returns mapping,
        #              second call (CanonicalRepRow) returns None → triggers query
        session.get.side_effect = [mapping, None]
        session.query.return_value.filter_by.return_value.first.return_value = _canonical_rep_row()
        repo = PostgresIdentityRepository(session)
        rep = repo.find_rep_by_lis_id("S001")
        assert rep is not None
        assert rep.bioguide_id == "A000370"

    def test_find_rep_by_lis_id_no_mapping(self):
        from adapters.postgres.identity_repo import PostgresIdentityRepository
        session = _make_session()
        session.get.return_value = None
        repo = PostgresIdentityRepository(session)
        assert repo.find_rep_by_lis_id("S999") is None

    def test_save_lis_bioguide_mapping_creates_entry(self):
        from adapters.postgres.identity_repo import PostgresIdentityRepository
        session = _make_session()
        session.get.return_value = None  # no existing mapping
        repo = PostgresIdentityRepository(session)
        repo.save_lis_bioguide_mapping("S001", "A000370", "Alma Adams", "NC", "D")
        session.add.assert_called_once()
        session.flush.assert_called_once()

    def test_save_lis_bioguide_mapping_skips_duplicate(self):
        from adapters.postgres.identity_repo import PostgresIdentityRepository
        from adapters.postgres.orm_models import LisBioguideMapRow
        session = _make_session()
        session.get.return_value = MagicMock(spec=LisBioguideMapRow)  # already exists
        repo = PostgresIdentityRepository(session)
        repo.save_lis_bioguide_mapping("S001", "A000370", "Alma Adams", "NC", "D")
        session.add.assert_not_called()

    def test_find_donor_by_fec_id_found(self):
        from adapters.postgres.identity_repo import PostgresIdentityRepository
        session = _make_session()
        session.query.return_value.all.return_value = [
            _canonical_donor_row('["C001", "C002"]'),
            _canonical_donor_row('["C003"]'),
        ]
        repo = PostgresIdentityRepository(session)
        donor = repo.find_donor_by_fec_id("C002")
        assert donor is not None
        assert donor.name == "GOOGLE"

    def test_find_donor_by_fec_id_not_found(self):
        from adapters.postgres.identity_repo import PostgresIdentityRepository
        session = _make_session()
        session.query.return_value.all.return_value = [
            _canonical_donor_row('["C001"]'),
        ]
        repo = PostgresIdentityRepository(session)
        assert repo.find_donor_by_fec_id("C999") is None

    def test_get_donor_maps_row(self):
        from adapters.postgres.identity_repo import PostgresIdentityRepository
        from domain.identity.models import DonorId, DonorType
        session = _make_session()
        session.get.return_value = _canonical_donor_row()
        repo = PostgresIdentityRepository(session)
        donor = repo.get_donor(DonorId("01DONOR"))
        assert donor is not None
        assert donor.name == "GOOGLE"
        assert donor.donor_type == DonorType.PAC
        assert "C001" in donor.fec_ids


# ── resolve_identities helpers ────────────────────────────────────────────────


class TestResolveIdentitiesHelpers:
    def test_extract_party_from_party_name(self):
        from pipeline.tasks.resolve_identities import _extract_party
        assert _extract_party({"partyName": "Democrat"}, {}) == "D"
        assert _extract_party({"partyName": "Republican"}, {}) == "R"

    def test_extract_party_from_party_field(self):
        from pipeline.tasks.resolve_identities import _extract_party
        assert _extract_party({"party": "D"}, {}) == "D"

    def test_extract_party_from_term(self):
        from pipeline.tasks.resolve_identities import _extract_party
        assert _extract_party({}, {"partyCode": "R"}) == "R"

    def test_extract_party_defaults_to_other(self):
        from pipeline.tasks.resolve_identities import _extract_party
        assert _extract_party({}, {}) == "O"

    def test_extract_district_house_int(self):
        from pipeline.tasks.resolve_identities import _extract_district
        result = _extract_district({"state": "NC", "district": 12}, {}, "House")
        assert result == "NC-12"

    def test_extract_district_house_str(self):
        from pipeline.tasks.resolve_identities import _extract_district
        result = _extract_district({"state": "CA", "district": "5"}, {}, "house")
        assert result == "CA-5"

    def test_extract_district_senate_always_none(self):
        from pipeline.tasks.resolve_identities import _extract_district
        assert _extract_district({"state": "NC", "district": 1}, {}, "Senate") is None
        assert _extract_district({"state": "NC", "district": 1}, {}, "senate") is None

    def test_extract_district_missing_info(self):
        from pipeline.tasks.resolve_identities import _extract_district
        assert _extract_district({}, {}, "House") is None


# ── CongressGovClient helpers ─────────────────────────────────────────────────


class TestCongressGovClientHelpers:
    def test_extract_list_finds_first_list_value(self):
        from adapters.external.congress_client import _extract_list
        body = {
            "pagination": {"count": 5},
            "request": {},
            "houseRollCallVotes": [{"rollCallNumber": 1}, {"rollCallNumber": 2}],
        }
        result = _extract_list(body)
        assert len(result) == 2
        assert result[0]["rollCallNumber"] == 1

    def test_extract_list_skips_pagination_and_request(self):
        from adapters.external.congress_client import _extract_list
        body = {"pagination": {"count": 1}, "request": {}, "members": [{"name": "Adams"}]}
        result = _extract_list(body)
        assert result == [{"name": "Adams"}]

    def test_extract_list_returns_empty_when_no_list(self):
        from adapters.external.congress_client import _extract_list
        assert _extract_list({"pagination": {}, "request": {}}) == []

    def test_get_house_vote_members_extracts_results(self):
        from unittest.mock import patch
        from adapters.external.congress_client import CongressGovClient
        member_data = [
            {"bioguideID": "A000370", "firstName": "Alma", "lastName": "Adams", "voteCast": "Yea"},
        ]
        fake_response = {
            "houseRollCallVoteMemberVotes": {
                "congress": 119,
                "results": member_data,
            }
        }
        with patch.object(CongressGovClient, "_get", return_value=fake_response):
            client = CongressGovClient.__new__(CongressGovClient)
            members = client.get_house_vote_members(119, 1, 42)
        assert len(members) == 1
        assert members[0]["bioguideID"] == "A000370"
        assert members[0]["voteCast"] == "Yea"

    def test_get_house_vote_members_empty_when_no_wrapper(self):
        from unittest.mock import patch
        from adapters.external.congress_client import CongressGovClient
        with patch.object(CongressGovClient, "_get", return_value={}):
            client = CongressGovClient.__new__(CongressGovClient)
            members = client.get_house_vote_members(119, 1, 999)
        assert members == []


# ── SenateXmlClient HTTP layer ────────────────────────────────────────────────


class TestSenateXmlClientHttp:
    """Test that HTTP responses are correctly routed to the XML parsers."""

    from tests.unit.test_sprint2 import _VOTE_LIST_XML, _VOTE_DETAIL_XML

    def test_get_vote_list_parses_response(self):
        from unittest.mock import MagicMock, patch
        from adapters.external.senate_xml_client import SenateXmlClient
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = self._VOTE_LIST_XML
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.Client.get", return_value=mock_response):
            client = SenateXmlClient()
            votes = client.get_vote_list(119, 1)
        assert len(votes) == 1
        assert votes[0]["roll_call"] == 1
        assert votes[0]["result"] == "Confirmed"

    def test_get_vote_detail_parses_response(self):
        from unittest.mock import MagicMock, patch
        from adapters.external.senate_xml_client import SenateXmlClient
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = self._VOTE_DETAIL_XML
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.Client.get", return_value=mock_response):
            client = SenateXmlClient()
            detail = client.get_vote_detail(119, 1, 1)
        assert detail["congress"] == 119
        assert len(detail["members"]) == 1
        assert detail["members"][0]["vote_cast"] == "Yea"

    def test_get_vote_list_raises_on_404(self):
        import pytest
        from unittest.mock import MagicMock, patch
        from adapters.external.senate_xml_client import SenateXmlClient, SenateXmlError
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.url = "https://www.senate.gov/test.xml"
        with patch("httpx.Client.get", return_value=mock_response):
            client = SenateXmlClient()
            with pytest.raises(SenateXmlError, match="not found"):
                client.get_vote_list(999, 1)

    def test_get_all_vote_details_skips_on_error(self):
        from unittest.mock import MagicMock, patch
        from adapters.external.senate_xml_client import SenateXmlClient, SenateXmlError
        client = SenateXmlClient.__new__(SenateXmlClient)
        client._client = MagicMock()
        with patch.object(client, "get_vote_list", return_value=[{"roll_call": 1}]):
            with patch.object(client, "get_vote_detail", side_effect=SenateXmlError("not found")):
                results = list(client.get_all_vote_details(119, 1))
        assert results == []  # skipped, no crash
