"""
Sprint 2 unit tests — FEC client mapping, alerting, staleness tracker, ingest task helpers.

These tests use mocking to avoid real network calls or Redis/DB connections.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


# ── FEC client ────────────────────────────────────────────────────────────────


class TestFECApiClientMapping:
    """Test the domain mapping helpers in ingest_fec (pure logic, no network)."""

    def test_map_to_domain_basic(self):
        from pipeline.tasks.ingest_fec import _map_to_domain

        record = {
            "transaction_id": "TXN001",
            "committee_id": "C00123456",
            "contributor_name": "Jane Smith",
            "contributor_employer": "Acme Corp",
            "contributor_occupation": "Engineer",
            "contributor_state": "CA",
            "contribution_receipt_amount": 2500.0,
            "contribution_receipt_date": "2024-03-15",
            "two_year_transaction_period": 2024,
        }
        filing = _map_to_domain(record)

        assert filing.source == "fec_api"
        assert filing.source_id == "TXN001"
        assert filing.committee_id == "C00123456"
        assert filing.contributor_name == "Jane Smith"
        assert filing.amount_cents == 250_000  # $2500.00 → 250000 cents
        assert filing.contribution_date == "2024-03-15"
        assert filing.election_cycle == 2024
        assert filing.payload is record  # verbatim API payload stored
        assert filing.is_processed is False

    def test_map_to_domain_handles_none_fields(self):
        from pipeline.tasks.ingest_fec import _map_to_domain

        record = {
            "transaction_id": "TXN002",
            "contribution_receipt_amount": None,
            "contributor_name": None,
            "contributor_employer": None,
        }
        filing = _map_to_domain(record)
        assert filing.amount_cents == 0
        assert filing.contributor_name == ""
        assert filing.contributor_employer == ""

    def test_map_to_domain_fractional_cents(self):
        from pipeline.tasks.ingest_fec import _map_to_domain

        record = {"transaction_id": "TXN003", "contribution_receipt_amount": 1.99}
        filing = _map_to_domain(record)
        assert filing.amount_cents == 199

    def test_current_election_cycle_119th_congress(self):
        from pipeline.tasks.ingest_fec import _current_election_cycle

        # 119th Congress (2025–2026) → cycle 2024 (the two_year_transaction_period
        # uses the even year at end of Congress)
        assert _current_election_cycle(119) == 1786 + (119 * 2)

    def test_to_row_dict_keys(self):
        from domain.ingestion.models import RawFiling
        from pipeline.tasks.ingest_fec import _to_row_dict

        filing = RawFiling(id="01TEST", source_id="TXN999")
        row = _to_row_dict(filing)
        expected_keys = {
            "id", "source", "source_id", "committee_id",
            "contributor_name", "contributor_employer", "contributor_occupation",
            "contributor_state", "amount_cents", "contribution_date",
            "election_cycle", "payload", "fetched_at", "is_processed",
        }
        assert set(row.keys()) == expected_keys


# ── ingest_votes mapping (Congress.gov + Senate XML) ──────────────────────────


class TestIngestVotesMapping:
    def test_map_house_member_basic(self):
        from pipeline.tasks.ingest_votes import _map_house_member

        # Actual Congress.gov API field names (confirmed from live API)
        member = {
            "bioguideID": "A000370",
            "firstName": "Jane",
            "lastName": "Smith",
            "voteParty": "D",
            "voteState": "NC",
            "voteCast": "Yea",
        }
        vote_summary = {"startDate": "2025-02-10T14:00:00-05:00", "result": "Passed"}
        bill_info = {"number": "42", "type": "HR", "title": "Some Act"}

        raw_vote = _map_house_member(
            member,
            vote_summary=vote_summary,
            bill_info=bill_info,
            congress=119,
            session_num=1,
            roll_call=42,
            vote_date="2025-02-10T14:00:00-05:00",
            source_id="house/119/1/42",
        )

        assert raw_vote.source == "congress_api"
        assert raw_vote.source_id == "house/119/1/42"
        assert raw_vote.member_bioguide_id == "A000370"
        assert raw_vote.member_name == "Jane Smith"
        assert raw_vote.position == "Yea"
        assert raw_vote.congress == 119
        assert raw_vote.chamber == "House"
        assert raw_vote.roll_call == 42
        assert raw_vote.bill_id == "42"
        assert raw_vote.voted_at == "2025-02-10"  # truncated to date
        assert raw_vote.is_processed is False

    def test_map_senate_member_basic(self):
        from pipeline.tasks.ingest_votes import _map_senate_member

        member = {
            "member_full": "Smith, Jane",
            "last_name": "Smith",
            "first_name": "Jane",
            "party": "D",
            "state": "NC",
            "lis_member_id": "S001",
            "vote_cast": "Yea",
        }
        vote_detail = {
            "congress": 119,
            "session": 1,
            "roll_call": 7,
            "vote_date": "15-Jan",
            "question": "On the Nomination",
            "bill_id": "PN373",
            "bill_title": "Some Nominee",
            "members": [],
        }

        raw_vote = _map_senate_member(
            member,
            vote_detail=vote_detail,
            congress=119,
            session_num=1,
            roll_call=7,
            source_id="senate/119/1/7",
        )

        assert raw_vote.source == "senate_xml"
        assert raw_vote.source_id == "senate/119/1/7"
        assert raw_vote.member_bioguide_id == "S001"  # lis_member_id until Sprint 3
        assert raw_vote.member_name == "Smith, Jane"
        assert raw_vote.position == "Yea"
        assert raw_vote.chamber == "Senate"
        assert raw_vote.roll_call == 7
        assert raw_vote.bill_id == "PN373"

    def test_normalize_senate_date(self):
        from pipeline.tasks.ingest_votes import _normalize_senate_date

        # 119th Congress starts 2025
        assert _normalize_senate_date("15-Jan", 119) == "2025-01-15"
        assert _normalize_senate_date("18-Dec", 119) == "2025-12-18"
        assert _normalize_senate_date("", 119) == ""

    def test_to_row_dict_keys(self):
        from domain.ingestion.models import RawVote
        from pipeline.tasks.ingest_votes import _to_row_dict

        vote = RawVote(id="01VOTE", source_id="senate/119/1/1", member_bioguide_id="S001")
        row = _to_row_dict(vote)
        expected_keys = {
            "id", "source", "source_id", "congress", "session", "chamber",
            "roll_call", "bill_id", "bill_title", "member_bioguide_id",
            "member_name", "position", "voted_at", "payload", "fetched_at", "is_processed",
        }
        assert set(row.keys()) == expected_keys


# ── Senate XML parser ─────────────────────────────────────────────────────────

_VOTE_LIST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<vote_summary>
  <congress>119</congress>
  <session>1</session>
  <votes>
    <vote>
      <vote_number>00001</vote_number>
      <vote_date>15-Jan</vote_date>
      <issue>PN373</issue>
      <question>On the Nomination</question>
      <result>Confirmed</result>
      <title>John Smith to be Secretary of Foo</title>
      <vote_tally><yeas>84</yeas><nays>9</nays></vote_tally>
    </vote>
  </votes>
</vote_summary>"""

_VOTE_DETAIL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<roll_call_vote>
  <congress>119</congress>
  <session>1</session>
  <vote_number>1</vote_number>
  <vote_date>January 15, 2025 02:30 PM</vote_date>
  <question>On the Nomination</question>
  <vote_title>Nomination of John Smith</vote_title>
  <vote_result>Confirmed</vote_result>
  <vote_question_text>Will the Senate confirm?</vote_question_text>
  <vote_document_text>PN373</vote_document_text>
  <document>
    <document_number>PN373</document_number>
    <document_title>John Smith Nomination</document_title>
  </document>
  <count><yeas>84</yeas><nays>9</nays><present>0</present><absent>7</absent></count>
  <members>
    <member>
      <member_full>Smith, Jane</member_full>
      <last_name>Smith</last_name>
      <first_name>Jane</first_name>
      <party>D</party>
      <state>NC</state>
      <lis_member_id>S001</lis_member_id>
      <vote_cast>Yea</vote_cast>
    </member>
  </members>
</roll_call_vote>"""


class TestSenateXmlParser:
    def test_parse_vote_list(self):
        from adapters.external.senate_xml_client import _parse_vote_list

        votes = _parse_vote_list(_VOTE_LIST_XML)
        assert len(votes) == 1
        v = votes[0]
        assert v["roll_call"] == 1
        assert v["date"] == "15-Jan"
        assert v["issue"] == "PN373"
        assert v["question"] == "On the Nomination"
        assert v["result"] == "Confirmed"
        assert v["yeas"] == 84
        assert v["nays"] == 9

    def test_parse_vote_detail(self):
        from adapters.external.senate_xml_client import _parse_vote_detail

        detail = _parse_vote_detail(_VOTE_DETAIL_XML)
        assert detail["congress"] == 119
        assert detail["session"] == 1
        assert detail["roll_call"] == 1
        assert detail["yeas"] == 84
        assert detail["nays"] == 9
        assert detail["absent"] == 7
        assert detail["bill_id"] == "PN373"
        assert detail["bill_title"] == "John Smith Nomination"

        members = detail["members"]
        assert len(members) == 1
        m = members[0]
        assert m["member_full"] == "Smith, Jane"
        assert m["party"] == "D"
        assert m["state"] == "NC"
        assert m["lis_member_id"] == "S001"
        assert m["vote_cast"] == "Yea"

    def test_parse_vote_list_invalid_xml(self):
        from adapters.external.senate_xml_client import SenateXmlError, _parse_vote_list

        with pytest.raises(SenateXmlError, match="Failed to parse"):
            _parse_vote_list("not xml at all")


# ── Staleness tracker ─────────────────────────────────────────────────────────


class TestStalenessTracker:
    def test_is_stale_when_no_key(self):
        from pipeline.monitoring.staleness_tracker import StalenessTracker

        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        with patch("pipeline.monitoring.staleness_tracker.get_redis_client", return_value=mock_redis):
            tracker = StalenessTracker()
            assert tracker.is_stale() is True

    def test_is_stale_when_recent(self):
        from pipeline.monitoring.staleness_tracker import StalenessTracker

        mock_redis = MagicMock()
        recent = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        mock_redis.get.return_value = recent
        with patch("pipeline.monitoring.staleness_tracker.get_redis_client", return_value=mock_redis):
            tracker = StalenessTracker()
            assert tracker.is_stale() is False

    def test_is_stale_when_old(self):
        from pipeline.monitoring.staleness_tracker import StalenessTracker

        mock_redis = MagicMock()
        old = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        mock_redis.get.return_value = old
        with patch("pipeline.monitoring.staleness_tracker.get_redis_client", return_value=mock_redis):
            tracker = StalenessTracker()
            assert tracker.is_stale() is True

    def test_record_success_sets_key(self):
        from pipeline.monitoring.staleness_tracker import StalenessTracker

        mock_redis = MagicMock()
        with patch("pipeline.monitoring.staleness_tracker.get_redis_client", return_value=mock_redis):
            StalenessTracker().record_success()
            mock_redis.set.assert_called_once()
            key, value = mock_redis.set.call_args[0]
            assert key == "pipeline:last_updated"
            # value should be a parseable ISO datetime
            parsed = datetime.fromisoformat(value)
            assert parsed.tzinfo is not None

    def test_get_last_updated_returns_datetime(self):
        from pipeline.monitoring.staleness_tracker import StalenessTracker

        mock_redis = MagicMock()
        ts = datetime(2026, 3, 9, 2, 0, 0, tzinfo=timezone.utc).isoformat()
        mock_redis.get.return_value = ts
        with patch("pipeline.monitoring.staleness_tracker.get_redis_client", return_value=mock_redis):
            result = StalenessTracker().get_last_updated()
            assert isinstance(result, datetime)
            assert result.year == 2026


# ── Alerting ──────────────────────────────────────────────────────────────────


class TestAlerting:
    def test_failure_alert_logs_error(self, caplog):
        from pipeline.monitoring.alerting import send_pipeline_failure_alert

        with patch("pipeline.monitoring.alerting.get_settings") as mock_settings, \
             caplog.at_level(logging.ERROR, logger="pipeline.monitoring.alerting"):
            mock_settings.return_value.slack_webhook_url = ""
            mock_settings.return_value.alert_email_to = ""
            send_pipeline_failure_alert("ingest_fec", ValueError("test error"))

        assert "PIPELINE FAILURE" in caplog.text
        assert "ingest_fec" in caplog.text

    def test_failure_alert_sends_slack_when_configured(self):
        from pipeline.monitoring.alerting import send_pipeline_failure_alert

        with patch("pipeline.monitoring.alerting.get_settings") as mock_settings, \
             patch("pipeline.monitoring.alerting.httpx.post") as mock_post:
            mock_settings.return_value.slack_webhook_url = "https://hooks.slack.com/test"
            mock_settings.return_value.alert_email_to = ""
            mock_post.return_value.raise_for_status = MagicMock()

            send_pipeline_failure_alert("ingest_fec", ValueError("boom"))

            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            assert "hooks.slack.com" in call_kwargs[0][0]

    def test_failure_alert_skips_slack_when_not_configured(self):
        from pipeline.monitoring.alerting import send_pipeline_failure_alert

        with patch("pipeline.monitoring.alerting.get_settings") as mock_settings, \
             patch("pipeline.monitoring.alerting.httpx.post") as mock_post:
            mock_settings.return_value.slack_webhook_url = ""
            mock_settings.return_value.alert_email_to = ""

            send_pipeline_failure_alert("ingest_fec", ValueError("boom"))

            mock_post.assert_not_called()

    def test_slack_alert_failure_does_not_raise(self):
        """Alerting failures must never crash the caller."""
        from pipeline.monitoring.alerting import send_pipeline_failure_alert

        with patch("pipeline.monitoring.alerting.get_settings") as mock_settings, \
             patch("pipeline.monitoring.alerting.httpx.post", side_effect=Exception("network down")):
            mock_settings.return_value.slack_webhook_url = "https://hooks.slack.com/test"
            mock_settings.return_value.alert_email_to = ""
            # Should not raise despite Slack being unreachable
            send_pipeline_failure_alert("ingest_fec", ValueError("boom"))

    def test_success_alert_logs_info(self, caplog):
        from pipeline.monitoring.alerting import send_pipeline_success_alert

        with patch("pipeline.monitoring.alerting.get_settings") as mock_settings, \
             caplog.at_level(logging.INFO, logger="pipeline.monitoring.alerting"):
            mock_settings.return_value.slack_webhook_url = ""
            send_pipeline_success_alert("ingest_fec", rows_written=1234)

        assert "PIPELINE SUCCESS" in caplog.text
        assert "1234" in caplog.text


# ── Health check ──────────────────────────────────────────────────────────────


class TestHealthCheck:
    def test_check_all_includes_redis(self):
        from pipeline.monitoring.health_check import check_all

        with patch("pipeline.monitoring.health_check.check_postgres_health", return_value=True), \
             patch("pipeline.monitoring.health_check.check_neo4j_health", return_value=True), \
             patch("pipeline.monitoring.health_check.check_redis_health", return_value=True):
            result = check_all()

        assert "postgres" in result
        assert "neo4j" in result
        assert "redis" in result
        assert all(result.values())
