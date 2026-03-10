"""Unit tests for pure domain models — no DB, no HTTP."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime

import pytest

from domain.correlation.models import (
    AlignmentScore,
    AlignmentScoreId,
    ConfidenceLevel,
    CorrelationEvent,
    CorrelationEventId,
)
from domain.finance.models import (
    Contribution,
    ContributionId,
    ContributionType,
    DonorRepRelationship,
    RelationshipId,
)
from domain.identity.models import (
    CanonicalDonor,
    CanonicalDonorRef,
    CanonicalRep,
    CanonicalRepRef,
    Chamber,
    DonorId,
    DonorType,
    Party,
    RepId,
)
from domain.shared.election_cycle import ElectionCycle
from domain.shared.industry import INDUSTRY_DISPLAY_NAMES, Industry
from domain.voting.models import (
    Bill,
    BillId,
    BillRef,
    RollCallVote,
    Sponsorship,
    SponsorRole,
    VoteId,
    VotePosition,
    VoteType,
)
from domain.shared.money import Money
from datetime import date


# ── Money ─────────────────────────────────────────────────────────────────────

def test_money_from_dollars():
    m = Money.from_dollars(1234.56)
    assert m.cents == 123456
    assert m.dollars == 1234.56


def test_money_addition():
    a = Money.from_dollars(100)
    b = Money.from_dollars(50)
    assert (a + b).cents == 15000


def test_money_negative_raises():
    with pytest.raises(ValueError, match="negative"):
        Money(cents=-1)


def test_money_cross_currency_raises():
    with pytest.raises(ValueError, match="Cannot add"):
        Money(cents=100, currency="USD") + Money(cents=100, currency="EUR")


def test_money_repr():
    assert repr(Money.from_dollars(1000)) == "$1,000.00"


# ── ElectionCycle ─────────────────────────────────────────────────────────────

def test_election_cycle_label():
    assert ElectionCycle(2024).label == "2023–2024"


def test_election_cycle_start_year():
    assert ElectionCycle(2024).start_year == 2023


def test_election_cycle_odd_raises():
    with pytest.raises(ValueError, match="must be even"):
        ElectionCycle(2023)


def test_election_cycle_out_of_range():
    with pytest.raises(ValueError, match="out of range"):
        ElectionCycle(1970)


def test_election_cycle_current():
    cycle = ElectionCycle.current()
    assert cycle.year % 2 == 0


# ── DonorRepRelationship ──────────────────────────────────────────────────────

def _make_contribution(amount_dollars: float, on: date) -> Contribution:
    return Contribution(
        id=ContributionId("c1"),
        donor_id="donor1",
        representative_id="rep1",
        amount=Money.from_dollars(amount_dollars),
        contributed_on=on,
        election_cycle=ElectionCycle(2024),
        contribution_type=ContributionType.INDIVIDUAL,
    )


def test_relationship_add_contribution_updates_total():
    rel = DonorRepRelationship(
        id=RelationshipId("r1"),
        donor=CanonicalDonorRef(id=DonorId("d1"), name="ACME Corp"),
        representative=CanonicalRepRef(id=RepId("rep1"), full_name="Jane Smith"),
    )
    rel.add_contribution(_make_contribution(500, date(2024, 1, 15)))
    rel.add_contribution(_make_contribution(250, date(2024, 3, 20)))

    assert rel.total_amount.dollars == 750


def test_relationship_tracks_first_and_latest_donation():
    rel = DonorRepRelationship(
        id=RelationshipId("r1"),
        donor=CanonicalDonorRef(id=DonorId("d1"), name="ACME Corp"),
        representative=CanonicalRepRef(id=RepId("rep1"), full_name="Jane Smith"),
    )
    early = date(2022, 5, 1)
    late = date(2024, 10, 31)

    rel.add_contribution(_make_contribution(100, late))
    rel.add_contribution(_make_contribution(100, early))

    assert rel.first_donation == early
    assert rel.latest_donation == late


def test_relationship_deduplicates_cycles():
    rel = DonorRepRelationship(
        id=RelationshipId("r1"),
        donor=CanonicalDonorRef(id=DonorId("d1"), name="ACME Corp"),
        representative=CanonicalRepRef(id=RepId("rep1"), full_name="Jane Smith"),
    )
    rel.add_contribution(_make_contribution(100, date(2024, 1, 1)))
    rel.add_contribution(_make_contribution(100, date(2024, 6, 1)))  # same cycle

    assert len(rel.cycles) == 1
    assert rel.cycles[0] == ElectionCycle(2024)


# ── CanonicalRep ───────────────────────────────────────────────────────────────

def _make_rep(**overrides) -> CanonicalRep:
    defaults = dict(
        id=RepId("r1"),
        full_name="Jane Smith",
        party=Party.DEMOCRAT,
        chamber=Chamber.HOUSE,
        state="CA",
        district="CA-12",
        bioguide_id="S000001",
        fec_candidate_id="H1CA12001",
    )
    return CanonicalRep(**{**defaults, **overrides})


def test_canonical_rep_valid():
    rep = _make_rep()
    assert rep.full_name == "Jane Smith"
    assert rep.state == "CA"
    assert rep.party == Party.DEMOCRAT
    assert rep.chamber == Chamber.HOUSE


def test_canonical_rep_invalid_state_too_long():
    with pytest.raises(ValueError, match="2-letter"):
        _make_rep(state="CAL")


def test_canonical_rep_invalid_state_too_short():
    with pytest.raises(ValueError, match="2-letter"):
        _make_rep(state="C")


def test_canonical_rep_empty_name_raises():
    with pytest.raises(ValueError, match="empty"):
        _make_rep(full_name="   ")


def test_canonical_rep_ref_is_frozen():
    ref = CanonicalRepRef(id=RepId("r1"), full_name="Jane")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ref.full_name = "Bob"  # type: ignore[misc]


# ── CanonicalDonor ────────────────────────────────────────────────────────────

def test_canonical_donor_valid():
    donor = CanonicalDonor(
        id=DonorId("d1"),
        name="ACME Corp",
        donor_type=DonorType.CORPORATION,
        industry=Industry.FINANCE_INSURANCE_REAL_ESTATE,
        state="NY",
        fec_ids=["C00123456", "C00789012"],
    )
    assert donor.name == "ACME Corp"
    assert len(donor.fec_ids) == 2


def test_canonical_donor_empty_name_raises():
    with pytest.raises(ValueError, match="empty"):
        CanonicalDonor(
            id=DonorId("d1"),
            name="  ",
            donor_type=DonorType.INDIVIDUAL,
            industry=None,
            state=None,
        )


def test_canonical_donor_ref_is_frozen():
    ref = CanonicalDonorRef(id=DonorId("d1"), name="ACME")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ref.name = "Other"  # type: ignore[misc]


# ── Industry ──────────────────────────────────────────────────────────────────

def test_industry_is_str_enum():
    assert Industry.HEALTH == "health"
    assert Industry.DEFENSE == "defense"
    assert Industry.UNKNOWN == "unknown"


def test_industry_display_names_covers_all_values():
    for member in Industry:
        assert member in INDUSTRY_DISPLAY_NAMES, f"{member} missing from INDUSTRY_DISPLAY_NAMES"
        assert INDUSTRY_DISPLAY_NAMES[member]  # non-empty string


# ── Voting models ─────────────────────────────────────────────────────────────

def test_bill_defaults():
    bill = Bill(id=BillId("b1"), title="Healthcare Reform Act")
    assert bill.industries == []
    assert bill.nlp_confidence == 0.0
    assert bill.congress is None
    assert bill.congress_gov_id is None


def test_bill_ref_is_frozen():
    ref = BillRef(id=BillId("b1"), title="Some Bill")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ref.title = "Other"  # type: ignore[misc]


def test_roll_call_vote_defaults_to_floor():
    vote = RollCallVote(
        id=VoteId("v1"),
        bill=BillRef(id=BillId("b1"), title="Tax Reform Act"),
        representative=CanonicalRepRef(id=RepId("r1"), full_name="Jane Smith"),
        position=VotePosition.YES,
        voted_at=datetime(2024, 3, 15, 14, 0),
    )
    assert vote.vote_type == VoteType.FLOOR
    assert vote.position == VotePosition.YES


def test_vote_position_values():
    assert VotePosition.YES == "yes"
    assert VotePosition.NO == "no"
    assert VotePosition.ABSTAIN == "abstain"
    assert VotePosition.NOT_VOTING == "not_voting"


def test_sponsorship_creation():
    sp = Sponsorship(
        bill=BillRef(id=BillId("b1"), title="Defense Authorization Act"),
        representative=CanonicalRepRef(id=RepId("r1"), full_name="Jane Smith"),
        role=SponsorRole.COSPONSOR,
    )
    assert sp.role == SponsorRole.COSPONSOR


# ── AlignmentScore ────────────────────────────────────────────────────────────

def _make_alignment_score(evidence_count: int, shift: float, p_value: float) -> AlignmentScore:
    return AlignmentScore(
        id=AlignmentScoreId("as1"),
        representative=CanonicalRepRef(id=RepId("r1"), full_name="Jane Smith"),
        donor=CanonicalDonorRef(id=DonorId("d1"), name="Oil PAC"),
        industry=Industry.ENERGY_NATURAL_RESOURCES,
        score=0.75,
        confidence=ConfidenceLevel.HIGH,
        evidence_count=evidence_count,
        before_score=0.50,
        after_score=0.50 + shift,
        shift=shift,
        p_value=p_value,
        methodology_url="http://localhost:3000/methodology",
    )


def test_alignment_score_significant_when_all_thresholds_met():
    assert _make_alignment_score(evidence_count=10, shift=0.20, p_value=0.01).is_significant()


def test_alignment_score_not_significant_low_evidence():
    assert not _make_alignment_score(evidence_count=4, shift=0.20, p_value=0.01).is_significant()


def test_alignment_score_not_significant_small_shift():
    assert not _make_alignment_score(evidence_count=10, shift=0.10, p_value=0.01).is_significant()


def test_alignment_score_not_significant_high_p_value():
    assert not _make_alignment_score(evidence_count=10, shift=0.20, p_value=0.05).is_significant()


def test_alignment_score_significant_negative_shift():
    # Voting less aligned after donation is also a meaningful signal
    assert _make_alignment_score(evidence_count=10, shift=-0.20, p_value=0.01).is_significant()


def test_alignment_score_not_significant_zero_shift():
    assert not _make_alignment_score(evidence_count=10, shift=0.0, p_value=0.01).is_significant()


def test_alignment_score_significant_at_exact_boundaries():
    # evidence_count=5, |shift|=0.15, p_value=0.049 — should pass all three
    assert _make_alignment_score(evidence_count=5, shift=0.15, p_value=0.049).is_significant()


def test_alignment_score_not_significant_evidence_one_below_threshold():
    assert not _make_alignment_score(evidence_count=4, shift=0.15, p_value=0.049).is_significant()


# ── CorrelationEvent ──────────────────────────────────────────────────────────

def _make_correlation_event(**overrides) -> CorrelationEvent:
    defaults = dict(
        id=CorrelationEventId("ce1"),
        representative=CanonicalRepRef(id=RepId("r1"), full_name="Jane Smith"),
        donor=CanonicalDonorRef(id=DonorId("d1"), name="Oil PAC"),
        industry=Industry.ENERGY_NATURAL_RESOURCES,
        event_date=date(2022, 6, 15),
        threshold_amount=Money.from_dollars(50_000),
    )
    return CorrelationEvent(**{**defaults, **overrides})


def test_correlation_event_creation():
    event = _make_correlation_event()
    assert event.id == CorrelationEventId("ce1")
    assert event.industry == Industry.ENERGY_NATURAL_RESOURCES
    assert event.event_date == date(2022, 6, 15)
    assert event.threshold_amount.dollars == 50_000


def test_correlation_event_threshold_amount_is_money():
    event = _make_correlation_event(threshold_amount=Money.from_dollars(100_000))
    assert isinstance(event.threshold_amount, Money)
    assert event.threshold_amount.cents == 10_000_000


def test_correlation_event_id_is_string_compatible():
    # CorrelationEventId is a NewType over str — usable as a string
    event_id = CorrelationEventId("ce-abc-123")
    assert isinstance(event_id, str)
    assert event_id == "ce-abc-123"


def test_correlation_event_links_rep_and_donor():
    event = _make_correlation_event(
        representative=CanonicalRepRef(id=RepId("r99"), full_name="Bob Jones"),
        donor=CanonicalDonorRef(id=DonorId("d99"), name="Finance PAC"),
    )
    assert event.representative.full_name == "Bob Jones"
    assert event.donor.name == "Finance PAC"


def test_correlation_event_different_industries():
    for industry in [Industry.HEALTH, Industry.DEFENSE, Industry.FINANCE_INSURANCE_REAL_ESTATE]:
        event = _make_correlation_event(industry=industry)
        assert event.industry == industry
