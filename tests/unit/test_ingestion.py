"""Unit tests for the ingestion bounded context raw models."""

from __future__ import annotations

from datetime import timezone

from domain.ingestion.models import RawDonor, RawFiling, RawVote


def test_raw_filing_defaults():
    filing = RawFiling(id="01ABCDEF")
    assert filing.source == "fec_api"
    assert filing.source_id == ""
    assert filing.payload == {}
    assert filing.is_processed is False


def test_raw_filing_fetched_at_is_utc():
    filing = RawFiling(id="01ABCDEF")
    assert filing.fetched_at.tzinfo == timezone.utc


def test_raw_filing_stores_payload():
    payload = {"contributor_name": "Jane Smith", "contribution_receipt_amount": 2500.0}
    filing = RawFiling(id="01ABCDEF", source_id="TXN123", payload=payload)
    assert filing.payload["contributor_name"] == "Jane Smith"
    assert filing.source_id == "TXN123"


def test_raw_donor_defaults():
    donor = RawDonor(id="01XYZ")
    assert donor.source == "fec_api"
    assert donor.is_processed is False
    assert donor.payload == {}


def test_raw_donor_fetched_at_is_utc():
    donor = RawDonor(id="01XYZ")
    assert donor.fetched_at.tzinfo == timezone.utc


def test_raw_vote_defaults():
    vote = RawVote(id="01VOTE")
    assert vote.source == "congress_api"
    assert vote.is_processed is False
    assert vote.payload == {}


def test_raw_vote_fetched_at_is_utc():
    vote = RawVote(id="01VOTE")
    assert vote.fetched_at.tzinfo == timezone.utc


def test_raw_vote_stores_payload():
    payload = {"member_id": "A000001", "position": "Yes", "bill": {"bill_id": "hr1234-118"}}
    vote = RawVote(id="01VOTE", source_id="roll_call/118/h/1/5", payload=payload)
    assert vote.payload["position"] == "Yes"
    assert vote.source_id == "roll_call/118/h/1/5"


def test_raw_models_have_independent_payload_defaults():
    """Each instance must get its own payload dict, not a shared one."""
    a = RawFiling(id="01A")
    b = RawFiling(id="01B")
    a.payload["key"] = "value"
    assert "key" not in b.payload
