"""Unit tests for pure domain models — no DB, no HTTP."""

from __future__ import annotations

import pytest

from domain.finance.models import (
    Contribution,
    ContributionType,
    DonorRepRelationship,
    RelationshipId,
    ContributionId,
)
from domain.identity.models import (
    CanonicalDonorRef,
    CanonicalRepRef,
    DonorId,
    RepId,
)
from domain.shared.election_cycle import ElectionCycle
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
