"""
Public REST API router — Sprint 5 implements representatives, donors, and search.

Remaining stubs: votes (Sprint 7), correlations (Sprint 8), zip (Sprint 5 — needs
Google Civic API key), compare / export (Sprint 9).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from adapters.postgres.orm_models import (
    CanonicalDonorRow,
    CanonicalRelationshipRow,
    CanonicalRepRow,
)
from infrastructure.database import get_db

router = APIRouter(tags=["public"])


# ── Response models ────────────────────────────────────────────────────────────


class RepSummary(BaseModel):
    id: str
    full_name: str
    party: str
    chamber: str
    state: str
    district: Optional[str]
    bioguide_id: Optional[str]


class IndustrySummary(BaseModel):
    industry: str
    total_cents: int


class TopDonorSummary(BaseModel):
    donor_id: str
    donor_name: str
    total_cents: int
    donor_type: str


class RepProfile(BaseModel):
    id: str
    full_name: str
    party: str
    chamber: str
    state: str
    district: Optional[str]
    bioguide_id: Optional[str]
    total_raised_cents: int
    top_industries: list[IndustrySummary]
    top_donors: list[TopDonorSummary]


class DonorProfile(BaseModel):
    id: str
    name: str
    donor_type: str
    industry: Optional[str]
    state: Optional[str]
    total_given_cents: int


class DonorRecipient(BaseModel):
    rep_id: str
    rep_name: str
    party: str
    chamber: str
    state: str
    total_cents: int


class SearchResult(BaseModel):
    type: str  # "rep" or "donor"
    id: str
    name: str
    party: Optional[str]
    chamber: Optional[str]
    state: Optional[str]
    donor_type: Optional[str]


# ── Helpers ────────────────────────────────────────────────────────────────────


def _rep_summary(row: CanonicalRepRow) -> RepSummary:
    return RepSummary(
        id=row.id,
        full_name=row.full_name,
        party=row.party,
        chamber=row.chamber,
        state=row.state,
        district=row.district,
        bioguide_id=row.bioguide_id,
    )


# ── Representatives ────────────────────────────────────────────────────────────


@router.get("/representatives", response_model=list[RepSummary], summary="List representatives")
def list_representatives(
    state: str | None = None,
    chamber: str | None = None,
    party: str | None = None,
    db: Session = Depends(get_db),
):
    """Filter by state (2-letter), chamber (house/senate), party (D/R/I/O)."""
    q = db.query(CanonicalRepRow)
    if state:
        q = q.filter(CanonicalRepRow.state == state.upper())
    if chamber:
        q = q.filter(CanonicalRepRow.chamber == chamber.lower())
    if party:
        # Accept full word ("Democrat") or single letter ("D")
        q = q.filter(CanonicalRepRow.party == party.upper()[0])
    return [
        _rep_summary(r)
        for r in q.order_by(CanonicalRepRow.state, CanonicalRepRow.full_name)
        .limit(535)
        .all()
    ]


@router.get("/representatives/{rep_id}", response_model=RepProfile, summary="Get representative profile")
def get_representative(rep_id: str, db: Session = Depends(get_db)):
    """Full profile with funding summary, top industries, and top donors."""
    rep = db.get(CanonicalRepRow, rep_id)
    if rep is None:
        raise HTTPException(status_code=404, detail="Representative not found")

    total_raised_cents = int(
        db.execute(
            text(
                "SELECT COALESCE(SUM(total_amount_cents), 0) "
                "FROM canonical_donor_rep_relationships WHERE rep_id = :rep_id"
            ),
            {"rep_id": rep_id},
        ).scalar()
        or 0
    )

    industry_rows = db.execute(
        text("""
            SELECT cd.industry, SUM(r.total_amount_cents) AS total_cents
            FROM canonical_donor_rep_relationships r
            JOIN canonical_donors cd ON cd.id = r.donor_id
            WHERE r.rep_id = :rep_id AND cd.industry IS NOT NULL
            GROUP BY cd.industry
            ORDER BY total_cents DESC
            LIMIT 10
        """),
        {"rep_id": rep_id},
    ).fetchall()

    donor_rows = db.execute(
        text("""
            SELECT r.donor_id, cd.name, cd.donor_type, SUM(r.total_amount_cents) AS total_cents
            FROM canonical_donor_rep_relationships r
            JOIN canonical_donors cd ON cd.id = r.donor_id
            WHERE r.rep_id = :rep_id
            GROUP BY r.donor_id, cd.name, cd.donor_type
            ORDER BY total_cents DESC
            LIMIT 10
        """),
        {"rep_id": rep_id},
    ).fetchall()

    return RepProfile(
        id=rep.id,
        full_name=rep.full_name,
        party=rep.party,
        chamber=rep.chamber,
        state=rep.state,
        district=rep.district,
        bioguide_id=rep.bioguide_id,
        total_raised_cents=total_raised_cents,
        top_industries=[
            IndustrySummary(industry=row[0], total_cents=int(row[1]))
            for row in industry_rows
        ],
        top_donors=[
            TopDonorSummary(
                donor_id=row[0],
                donor_name=row[1],
                donor_type=row[2],
                total_cents=int(row[3]),
            )
            for row in donor_rows
        ],
    )


@router.get("/representatives/{rep_id}/votes", summary="Get voting record")
def get_representative_votes(rep_id: str):
    """TODO Sprint 7: Voting record with industry tags."""
    raise HTTPException(status_code=501, detail="Implemented in Sprint 7")


@router.get("/representatives/{rep_id}/correlations", summary="Get alignment scores")
def get_representative_correlations(rep_id: str):
    """TODO Sprint 8: AlignmentScore list with shift and confidence."""
    raise HTTPException(status_code=501, detail="Implemented in Sprint 8")


# ── Donors ─────────────────────────────────────────────────────────────────────


@router.get("/donors/{donor_id}", response_model=DonorProfile, summary="Get donor profile")
def get_donor(donor_id: str, db: Session = Depends(get_db)):
    """Donor profile with total giving and industry."""
    donor = db.get(CanonicalDonorRow, donor_id)
    if donor is None:
        raise HTTPException(status_code=404, detail="Donor not found")

    total_given_cents = int(
        db.execute(
            text(
                "SELECT COALESCE(SUM(total_amount_cents), 0) "
                "FROM canonical_donor_rep_relationships WHERE donor_id = :donor_id"
            ),
            {"donor_id": donor_id},
        ).scalar()
        or 0
    )

    return DonorProfile(
        id=donor.id,
        name=donor.name,
        donor_type=donor.donor_type,
        industry=donor.industry,
        state=donor.state,
        total_given_cents=total_given_cents,
    )


@router.get("/donors/{donor_id}/recipients", response_model=list[DonorRecipient], summary="List reps funded by donor")
def get_donor_recipients(donor_id: str, db: Session = Depends(get_db)):
    """All representatives funded by this donor, sorted by total amount."""
    donor = db.get(CanonicalDonorRow, donor_id)
    if donor is None:
        raise HTTPException(status_code=404, detail="Donor not found")

    rows = db.execute(
        text("""
            SELECT r.rep_id, cr.full_name, cr.party, cr.chamber, cr.state,
                   r.total_amount_cents
            FROM canonical_donor_rep_relationships r
            JOIN canonical_reps cr ON cr.id = r.rep_id
            WHERE r.donor_id = :donor_id
            ORDER BY r.total_amount_cents DESC
        """),
        {"donor_id": donor_id},
    ).fetchall()

    return [
        DonorRecipient(
            rep_id=row[0],
            rep_name=row[1],
            party=row[2],
            chamber=row[3],
            state=row[4],
            total_cents=int(row[5]),
        )
        for row in rows
    ]


# ── Search ─────────────────────────────────────────────────────────────────────


@router.get("/search", response_model=list[SearchResult], summary="Search representatives and donors")
def search(q: str, db: Session = Depends(get_db)):
    """Name search across canonical reps and donors (case-insensitive LIKE)."""
    pattern = f"%{q}%"

    rep_rows = (
        db.query(CanonicalRepRow)
        .filter(CanonicalRepRow.full_name.ilike(pattern))
        .order_by(CanonicalRepRow.full_name)
        .limit(10)
        .all()
    )
    donor_rows = (
        db.query(CanonicalDonorRow)
        .filter(CanonicalDonorRow.name.ilike(pattern))
        .order_by(CanonicalDonorRow.name)
        .limit(10)
        .all()
    )

    results: list[SearchResult] = [
        SearchResult(
            type="rep",
            id=r.id,
            name=r.full_name,
            party=r.party,
            chamber=r.chamber,
            state=r.state,
            donor_type=None,
        )
        for r in rep_rows
    ]
    results += [
        SearchResult(
            type="donor",
            id=d.id,
            name=d.name,
            party=None,
            chamber=None,
            state=d.state,
            donor_type=d.donor_type,
        )
        for d in donor_rows
    ]
    return results


# ── Stubs (future sprints) ─────────────────────────────────────────────────────


@router.get("/zip/{zipcode}", summary="Get reps for ZIP code")
def zip_lookup(zipcode: str):
    """TODO Sprint 5: ZIP → district → reps. Requires GOOGLE_CIVIC_API_KEY."""
    raise HTTPException(status_code=501, detail="Requires Google Civic API key")


@router.get("/compare", summary="Side-by-side representative comparison")
def compare(ids: str):
    """TODO Sprint 9."""
    raise HTTPException(status_code=501, detail="Implemented in Sprint 9")


@router.get("/export/{rep_id}.csv", summary="Export representative data as CSV")
def export_csv(rep_id: str):
    """TODO Sprint 9."""
    raise HTTPException(status_code=501, detail="Implemented in Sprint 9")
