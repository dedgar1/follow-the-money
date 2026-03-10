"""
SQLAlchemy ORM models — separate from domain dataclasses per hexagonal architecture.

These are the persistence representations. Domain models are pure Python dataclasses
in domain/*/models.py. Mapping between them happens in repository adapters.
"""

from __future__ import annotations

from datetime import date, datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class RepresentativeRow(Base):
    __tablename__ = "representatives"

    id:                Mapped[str] = mapped_column(String(26), primary_key=True)
    full_name:         Mapped[str] = mapped_column(String(255), nullable=False)
    party:             Mapped[str] = mapped_column(String(1), nullable=False)
    chamber:           Mapped[str] = mapped_column(String(10), nullable=False)
    state:             Mapped[str] = mapped_column(String(2), nullable=False)
    district:          Mapped[str | None] = mapped_column(String(10), nullable=True)
    bioguide_id:       Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    fec_candidate_id:  Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    created_at:        Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at:        Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )

    contributions: Mapped[list[ContributionRow]] = relationship(
        back_populates="representative"
    )
    votes: Mapped[list[VoteRow]] = relationship(back_populates="representative")

    __table_args__ = (
        Index("ix_representatives_state", "state"),
        Index("ix_representatives_party", "party"),
        Index("ix_representatives_chamber", "chamber"),
    )


class DonorRow(Base):
    __tablename__ = "donors"

    id:         Mapped[str] = mapped_column(String(26), primary_key=True)
    name:       Mapped[str] = mapped_column(String(500), nullable=False)
    donor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    industry:   Mapped[str | None] = mapped_column(String(50), nullable=True)
    state:      Mapped[str | None] = mapped_column(String(2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )

    contributions: Mapped[list[ContributionRow]] = relationship(back_populates="donor")

    __table_args__ = (Index("ix_donors_industry", "industry"),)


class ContributionRow(Base):
    __tablename__ = "contributions"

    id:                Mapped[str] = mapped_column(String(26), primary_key=True)
    donor_id:          Mapped[str] = mapped_column(
        String(26), ForeignKey("donors.id"), nullable=False
    )
    representative_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("representatives.id"), nullable=False
    )
    amount_cents:      Mapped[int] = mapped_column(BigInteger, nullable=False)
    contributed_on:    Mapped[date] = mapped_column(nullable=False)
    election_cycle:    Mapped[int] = mapped_column(Integer, nullable=False)
    contribution_type: Mapped[str] = mapped_column(String(20), nullable=False)
    fec_filing_id:     Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at:        Mapped[datetime] = mapped_column(DateTime, default=_now)

    donor:          Mapped[DonorRow] = relationship(back_populates="contributions")
    representative: Mapped[RepresentativeRow] = relationship(back_populates="contributions")

    __table_args__ = (
        Index("ix_contributions_donor_id", "donor_id"),
        Index("ix_contributions_representative_id", "representative_id"),
        Index("ix_contributions_election_cycle", "election_cycle"),
        Index("ix_contributions_contributed_on", "contributed_on"),
    )


class RelationshipRow(Base):
    __tablename__ = "donor_rep_relationships"

    id:                   Mapped[str] = mapped_column(String(26), primary_key=True)
    donor_id:             Mapped[str] = mapped_column(
        String(26), ForeignKey("donors.id"), nullable=False
    )
    representative_id:    Mapped[str] = mapped_column(
        String(26), ForeignKey("representatives.id"), nullable=False
    )
    total_amount_cents:   Mapped[int] = mapped_column(BigInteger, default=0)
    first_donation_date:  Mapped[date | None] = mapped_column(nullable=True)
    latest_donation_date: Mapped[date | None] = mapped_column(nullable=True)
    created_at:           Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at:           Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )

    __table_args__ = (
        Index("ix_relationships_donor_id", "donor_id"),
        Index("ix_relationships_representative_id", "representative_id"),
        Index(
            "uq_relationships_donor_rep",
            "donor_id",
            "representative_id",
            unique=True,
        ),
    )


class BillRow(Base):
    __tablename__ = "bills"

    id:              Mapped[str] = mapped_column(String(26), primary_key=True)
    title:           Mapped[str] = mapped_column(Text, nullable=False)
    industries:      Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    nlp_confidence:  Mapped[float] = mapped_column(Float, default=0.0)
    congress:        Mapped[int | None] = mapped_column(Integer, nullable=True)
    congress_gov_id: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True)
    created_at:      Mapped[datetime] = mapped_column(DateTime, default=_now)

    votes: Mapped[list[VoteRow]] = relationship(back_populates="bill")


class VoteRow(Base):
    __tablename__ = "votes"

    id:                Mapped[str] = mapped_column(String(26), primary_key=True)
    bill_id:           Mapped[str] = mapped_column(
        String(26), ForeignKey("bills.id"), nullable=False
    )
    representative_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("representatives.id"), nullable=False
    )
    position:          Mapped[str] = mapped_column(String(15), nullable=False)
    voted_at:          Mapped[datetime] = mapped_column(DateTime, nullable=False)
    vote_type:         Mapped[str] = mapped_column(String(15), default="floor")
    created_at:        Mapped[datetime] = mapped_column(DateTime, default=_now)

    bill:           Mapped[BillRow] = relationship(back_populates="votes")
    representative: Mapped[RepresentativeRow] = relationship(back_populates="votes")

    __table_args__ = (
        Index("ix_votes_bill_id", "bill_id"),
        Index("ix_votes_representative_id", "representative_id"),
        Index("ix_votes_voted_at", "voted_at"),
    )


# ── Raw ingestion tables (Sprint 2) ──────────────────────────────────────────
# These tables are IMMUTABLE — rows are never updated after insert.
# They hold verbatim API payloads; canonical tables are built from them downstream.


class RawFilingRow(Base):
    """Raw FEC Schedule A contribution filing — one row per FEC transaction."""

    __tablename__ = "raw_filings"

    id:                    Mapped[str] = mapped_column(String(26), primary_key=True)
    source:                Mapped[str] = mapped_column(String(20), nullable=False, default="fec_api")
    source_id:             Mapped[str] = mapped_column(String(100), nullable=False)
    committee_id:          Mapped[str] = mapped_column(String(50), default="")
    contributor_name:      Mapped[str] = mapped_column(String(500), default="")
    contributor_employer:  Mapped[str] = mapped_column(String(500), default="")
    contributor_occupation: Mapped[str] = mapped_column(String(500), default="")
    contributor_state:     Mapped[str] = mapped_column(String(2), default="")
    amount_cents:          Mapped[int] = mapped_column(BigInteger, default=0)
    contribution_date:     Mapped[str] = mapped_column(String(10), default="")
    election_cycle:        Mapped[int] = mapped_column(Integer, default=0)
    payload:               Mapped[dict] = mapped_column(JSON, default=dict)
    fetched_at:            Mapped[datetime] = mapped_column(DateTime, default=_now)
    is_processed:          Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_raw_filings_source_source_id"),
        Index("ix_raw_filings_election_cycle", "election_cycle"),
        Index("ix_raw_filings_committee_id", "committee_id"),
        Index("ix_raw_filings_is_processed", "is_processed"),
    )


class RawVoteRow(Base):
    """Raw roll-call vote — one row per (member, roll_call). Source: congress_api or senate_xml."""

    __tablename__ = "raw_votes"

    id:                   Mapped[str] = mapped_column(String(26), primary_key=True)
    source:               Mapped[str] = mapped_column(String(20), nullable=False, default="congress_api")
    source_id:            Mapped[str] = mapped_column(String(300), nullable=False)
    congress:             Mapped[int] = mapped_column(Integer, default=0)
    session:              Mapped[int] = mapped_column(Integer, default=1)
    chamber:              Mapped[str] = mapped_column(String(10), default="")
    roll_call:            Mapped[int] = mapped_column(Integer, default=0)
    bill_id:              Mapped[str] = mapped_column(String(50), default="")
    bill_title:           Mapped[str] = mapped_column(Text, default="")
    member_bioguide_id:   Mapped[str] = mapped_column(String(20), default="")
    member_name:          Mapped[str] = mapped_column(String(255), default="")
    position:             Mapped[str] = mapped_column(String(20), default="")
    voted_at:             Mapped[str] = mapped_column(String(10), default="")
    payload:              Mapped[dict] = mapped_column(JSON, default=dict)
    fetched_at:           Mapped[datetime] = mapped_column(DateTime, default=_now)
    is_processed:         Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        # One position per (member, roll_call) — deduplicate on re-ingestion
        UniqueConstraint("source_id", "member_bioguide_id", name="uq_raw_votes_source_member"),
        Index("ix_raw_votes_congress", "congress"),
        Index("ix_raw_votes_member_bioguide_id", "member_bioguide_id"),
        Index("ix_raw_votes_is_processed", "is_processed"),
    )
