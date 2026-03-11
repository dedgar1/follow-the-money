"""
Public REST API router — fully implemented through Sprint 11.

Sprint 5: representatives, donors, search.
Sprint 7: voting record.
Sprint 8: alignment scores (correlations).
Sprint 9: compare, CSV export, ZIP lookup, embeddable widget.
Sprint 11: /stats, /ticker, JSON export, small-donor breakdown.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from adapters.postgres.orm_models import (
    CanonicalDonorRow,
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
    small_donor_cents: int
    top_industries: list[IndustrySummary]
    top_donors: list[TopDonorSummary]


class PlatformStats(BaseModel):
    total_reps: int
    total_donors: int
    total_raised_cents: int
    total_correlations: int


class TickerItem(BaseModel):
    contributor_name: str
    amount_cents: int
    committee_id: str
    contribution_date: Optional[str]


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


class NetworkNode(BaseModel):
    id: str
    type: str           # "rep" or "donor"
    label: str
    party: Optional[str] = None
    chamber: Optional[str] = None
    state: Optional[str] = None
    donor_type: Optional[str] = None
    is_center: bool = False


class NetworkEdge(BaseModel):
    source: str
    target: str
    total_cents: int
    cycles: list[int]


class NetworkGraph(BaseModel):
    nodes: list[NetworkNode]
    edges: list[NetworkEdge]


class VoteRecord(BaseModel):
    vote_id: str
    bill_id: str
    bill_title: str
    industries: list[str]    # Industry enum values, e.g. ["energy_natural_resources"]
    nlp_confidence: float
    position: str            # "yes" | "no" | "abstain" | "not_voting"
    voted_at: str            # "YYYY-MM-DD"
    chamber: str             # "house" | "senate"


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

    # Small donors: individual filings < $200 linked to this rep's donors
    small_donor_cents = int(
        db.execute(
            text("""
                SELECT COALESCE(SUM(rf.amount_cents), 0)
                FROM raw_filings rf
                JOIN canonical_donor_rep_relationships dr ON dr.donor_id = rf.canonical_donor_id
                WHERE dr.rep_id = :rep_id AND rf.amount_cents < 20000
            """),
            {"rep_id": rep_id},
        ).scalar()
        or 0
    )

    return RepProfile(
        id=rep.id,
        full_name=rep.full_name,
        party=rep.party,
        chamber=rep.chamber,
        state=rep.state,
        district=rep.district,
        bioguide_id=rep.bioguide_id,
        total_raised_cents=total_raised_cents,
        small_donor_cents=small_donor_cents,
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


@router.get("/representatives/{rep_id}/network", response_model=NetworkGraph, summary="Rep funding network graph")
def get_rep_network(rep_id: str, limit: int = 15, db: Session = Depends(get_db)):
    """2-hop network: rep → donors (hop-1) → sibling reps funded by those donors (hop-2)."""
    rep = db.get(CanonicalRepRow, rep_id)
    if rep is None:
        raise HTTPException(status_code=404, detail="Representative not found")
    try:
        from adapters.neo4j.network_query import NetworkQueryService
        return NetworkQueryService().get_rep_network(rep_id, direct_limit=limit)
    except Exception:
        return {"nodes": [], "edges": []}


@router.get("/representatives/{rep_id}/votes", response_model=list[VoteRecord], summary="Get voting record")
def get_representative_votes(rep_id: str, limit: int = 50, db: Session = Depends(get_db)):
    """
    Voting record for a representative, joined with bill industry tags.

    Reads from raw_votes via the rep's bioguide_id so data is available as
    soon as ingest_votes + classify_bills pipeline stages have run.
    Returns up to ``limit`` most recent votes (default 50, max 200).
    """
    rep = db.get(CanonicalRepRow, rep_id)
    if rep is None:
        raise HTTPException(status_code=404, detail="Representative not found")

    if not rep.bioguide_id:
        return []

    limit = min(limit, 200)
    rows = db.execute(
        text("""
            SELECT rv.id, rv.bill_id, rv.bill_title, rv.position,
                   rv.voted_at, rv.chamber,
                   b.industries, b.nlp_confidence
            FROM raw_votes rv
            LEFT JOIN bills b ON b.congress_gov_id = rv.bill_id
            WHERE rv.member_bioguide_id = :bioguide_id
            ORDER BY rv.voted_at DESC
            LIMIT :limit
        """),
        {"bioguide_id": rep.bioguide_id, "limit": limit},
    ).fetchall()

    return [_vote_record_from_row(row) for row in rows]


_POSITION_NORM: dict[str, str] = {
    "Yea": "yes", "Yes": "yes", "AYE": "yes",
    "Nay": "no", "No": "no", "NAY": "no",
    "Not Voting": "not_voting",
    "Present": "abstain", "Abstain": "abstain",
}


def _vote_record_from_row(row) -> VoteRecord:
    try:
        industries = json.loads(row[6] or "[]")
    except (json.JSONDecodeError, TypeError):
        industries = []
    return VoteRecord(
        vote_id=str(row[0]),
        bill_id=str(row[1] or ""),
        bill_title=str(row[2] or "Unknown bill"),
        industries=industries,
        nlp_confidence=float(row[7] or 0.0),
        position=_POSITION_NORM.get(str(row[3]), str(row[3]).lower()),
        voted_at=str(row[4])[:10] if row[4] else "",
        chamber=str(row[5] or "").lower(),
    )


class RepZipResult(BaseModel):
    id: str
    full_name: str
    party: str
    chamber: str
    state: str
    district: Optional[str]


class AlignmentScoreResponse(BaseModel):
    id: str
    industry: str
    score: float
    confidence: str          # "low" | "medium" | "high"
    evidence_count: int
    before_score: float
    after_score: float
    shift: float             # positive = more aligned after donation
    p_value: float
    methodology_url: str
    computed_at: Optional[str]


class ComparisonRepProfile(BaseModel):
    id: str
    full_name: str
    party: str
    chamber: str
    state: str
    district: Optional[str]
    total_raised_cents: int
    top_industries: list[IndustrySummary]
    top_donors: list[TopDonorSummary]
    alignment_scores: list[AlignmentScoreResponse]


class SharedDonorResponse(BaseModel):
    donor_id: str
    donor_name: str
    donor_type: str
    industry: Optional[str]
    amounts: dict[str, int]   # rep_id → cents


class ComparisonResponse(BaseModel):
    rep_ids: list[str]
    reps: list[ComparisonRepProfile]
    shared_donors: list[SharedDonorResponse]


@router.get(
    "/representatives/{rep_id}/correlations",
    response_model=list[AlignmentScoreResponse],
    summary="Get alignment scores",
)
def get_representative_correlations(rep_id: str, db: Session = Depends(get_db)):
    """
    Donor-industry alignment scores for a representative.

    Returns all AlignmentScores computed by the correlation pipeline for
    this rep, ordered by absolute shift magnitude (largest first).

    Only scores that passed all significance thresholds are stored:
      - evidence_count >= 5
      - |shift| >= 0.15
      - p_value < 0.05
    """
    from adapters.postgres.orm_models import AlignmentScoreRow

    rep = db.get(CanonicalRepRow, rep_id)
    if rep is None:
        raise HTTPException(status_code=404, detail="Representative not found")

    rows = (
        db.query(AlignmentScoreRow)
        .filter_by(rep_id=rep_id)
        .order_by(AlignmentScoreRow.shift.desc())
        .all()
    )

    return [
        AlignmentScoreResponse(
            id=row.id,
            industry=row.industry,
            score=row.score,
            confidence=row.confidence,
            evidence_count=row.evidence_count,
            before_score=row.before_score,
            after_score=row.after_score,
            shift=row.shift,
            p_value=row.p_value,
            methodology_url=row.methodology_url,
            computed_at=row.computed_at,
        )
        for row in rows
    ]


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


@router.get("/donors/{donor_id}/network", response_model=NetworkGraph, summary="Donor funding network graph")
def get_donor_network(donor_id: str, limit: int = 15, db: Session = Depends(get_db)):
    """2-hop network: donor → reps (hop-1) → sibling donors who also fund those reps (hop-2)."""
    donor = db.get(CanonicalDonorRow, donor_id)
    if donor is None:
        raise HTTPException(status_code=404, detail="Donor not found")
    try:
        from adapters.neo4j.network_query import NetworkQueryService
        return NetworkQueryService().get_donor_network(donor_id, direct_limit=limit)
    except Exception:
        return {"nodes": [], "edges": []}


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


# ── ZIP lookup ─────────────────────────────────────────────────────────────────

# Coarse ZIP-integer → state mapping.  Good enough for demo; a production
# deployment would call Google Civic Information API with an API key.
def _zip_to_state(zipcode: str) -> str | None:
    """Return 2-letter state code for a 5-digit ZIP, or None if unknown."""
    if not zipcode.isdigit() or len(zipcode) != 5:
        return None
    z = int(zipcode)
    if z < 1000:   return None
    if z < 2800:   return "MA"
    if z < 3000:   return "RI"
    if z < 3900:   return "NH"
    if z < 5000:   return "ME"
    if z < 5500:   return "VT"
    if z < 6999:   return "CT"
    if z < 9000:   return "NJ"
    if z < 14976:  return "NY"
    if z < 19641:  return "PA"
    if z < 19703:  return "DE"
    if z < 21931:  return "MD"
    if z < 22000:  return "DC"
    if z < 24701:  return "VA"
    if z < 25201:  return "WV"
    if z < 27500:  return "NC"
    if z < 29950:  return "SC"
    if z < 32000:  return "GA"
    if z < 35000:  return "FL"
    if z < 37000:  return "AL"
    if z < 38000:  return "TN"
    if z < 40000:  return "MS"
    if z < 41000:  return "KY"
    if z < 46000:  return "OH"
    if z < 48000:  return "IN"
    if z < 50000:  return "MI"
    if z < 55000:  return "WI"
    if z < 57000:  return "MN"
    if z < 59000:  return "ND"
    if z < 60000:  return "MT"
    if z < 62000:  return "IL"
    if z < 65000:  return "MO"
    if z < 67000:  return "KS"
    if z < 70000:  return "NE"
    if z < 73000:  return "AR"
    if z < 75000:  return "OK"
    if z < 80000:  return "TX"
    if z < 83000:  return "WY"
    if z < 84000:  return "ID"
    if z < 85000:  return "UT"
    if z < 86000:  return "AZ"
    if z < 88000:  return "NM"
    if z < 90000:  return "NV"
    if z < 96163:  return "CA"
    if z < 96800:  return "HI"
    if z <= 99950: return "AK"
    return None


@router.get("/zip/{zipcode}", response_model=list[RepSummary], summary="Get reps for ZIP code")
def zip_lookup(zipcode: str, db: Session = Depends(get_db)):
    """Returns representatives for the congressional state that contains this ZIP code."""
    if not zipcode.isdigit() or len(zipcode) != 5:
        raise HTTPException(status_code=422, detail="ZIP code must be 5 digits")
    state = _zip_to_state(zipcode)
    if not state:
        return []
    rows = (
        db.query(CanonicalRepRow)
        .filter(CanonicalRepRow.state == state)
        .order_by(CanonicalRepRow.chamber, CanonicalRepRow.full_name)
        .all()
    )
    return [_rep_summary(r) for r in rows]


# ── Compare ────────────────────────────────────────────────────────────────────


@router.get("/compare", response_model=ComparisonResponse, summary="Side-by-side comparison")
def compare(ids: str, db: Session = Depends(get_db)):
    """
    Compare 2–5 representatives.

    ``ids`` is a comma-separated list of canonical rep IDs, e.g.
    ``?ids=REP001,REP002``.  Returns per-rep profiles (funding, alignment)
    and a shared-donors table listing donors who funded all listed reps.
    """
    from adapters.postgres.orm_models import AlignmentScoreRow

    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    if len(id_list) < 2:
        raise HTTPException(status_code=422, detail="Provide at least 2 rep IDs (comma-separated)")
    if len(id_list) > 5:
        raise HTTPException(status_code=422, detail="Maximum 5 representatives per comparison")

    reps: list[CanonicalRepRow] = []
    for rep_id in id_list:
        rep = db.get(CanonicalRepRow, rep_id)
        if rep is None:
            raise HTTPException(status_code=404, detail=f"Representative not found: {rep_id}")
        reps.append(rep)

    # Build per-rep profiles
    rep_profiles: list[ComparisonRepProfile] = []
    donor_maps: list[dict[str, int]] = []

    for rep in reps:
        total_raised = int(
            db.execute(
                text("SELECT COALESCE(SUM(total_amount_cents),0) "
                     "FROM canonical_donor_rep_relationships WHERE rep_id=:rid"),
                {"rid": rep.id},
            ).scalar() or 0
        )
        industry_rows = db.execute(
            text("""
                SELECT cd.industry, SUM(r.total_amount_cents) AS total_cents
                FROM canonical_donor_rep_relationships r
                JOIN canonical_donors cd ON cd.id = r.donor_id
                WHERE r.rep_id = :rid AND cd.industry IS NOT NULL
                GROUP BY cd.industry ORDER BY total_cents DESC LIMIT 5
            """),
            {"rid": rep.id},
        ).fetchall()
        top_donor_rows = db.execute(
            text("""
                SELECT r.donor_id, cd.name, cd.donor_type, SUM(r.total_amount_cents) AS tc
                FROM canonical_donor_rep_relationships r
                JOIN canonical_donors cd ON cd.id = r.donor_id
                WHERE r.rep_id = :rid
                GROUP BY r.donor_id, cd.name, cd.donor_type
                ORDER BY tc DESC LIMIT 5
            """),
            {"rid": rep.id},
        ).fetchall()
        score_rows = (
            db.query(AlignmentScoreRow)
            .filter_by(rep_id=rep.id)
            .order_by(AlignmentScoreRow.shift.desc())
            .all()
        )

        # Collect this rep's donor map for shared-donor calculation
        dr_rows = db.execute(
            text("SELECT donor_id, total_amount_cents "
                 "FROM canonical_donor_rep_relationships WHERE rep_id=:rid"),
            {"rid": rep.id},
        ).fetchall()
        donor_maps.append({row[0]: int(row[1]) for row in dr_rows})

        rep_profiles.append(ComparisonRepProfile(
            id=rep.id,
            full_name=rep.full_name,
            party=rep.party,
            chamber=rep.chamber,
            state=rep.state,
            district=rep.district,
            total_raised_cents=total_raised,
            top_industries=[
                IndustrySummary(industry=r[0], total_cents=int(r[1]))
                for r in industry_rows
            ],
            top_donors=[
                TopDonorSummary(donor_id=r[0], donor_name=r[1], donor_type=r[2], total_cents=int(r[3]))
                for r in top_donor_rows
            ],
            alignment_scores=[
                AlignmentScoreResponse(
                    id=s.id, industry=s.industry, score=s.score,
                    confidence=s.confidence, evidence_count=s.evidence_count,
                    before_score=s.before_score, after_score=s.after_score,
                    shift=s.shift, p_value=s.p_value,
                    methodology_url=s.methodology_url, computed_at=s.computed_at,
                )
                for s in score_rows
            ],
        ))

    # Find donors shared across ALL reps
    shared_ids = set(donor_maps[0].keys())
    for m in donor_maps[1:]:
        shared_ids &= set(m.keys())

    shared_donors: list[SharedDonorResponse] = []
    for donor_id in shared_ids:
        donor = db.get(CanonicalDonorRow, donor_id)
        if donor:
            amounts = {reps[i].id: donor_maps[i].get(donor_id, 0) for i in range(len(reps))}
            shared_donors.append(SharedDonorResponse(
                donor_id=donor_id,
                donor_name=donor.name,
                donor_type=donor.donor_type,
                industry=donor.industry,
                amounts=amounts,
            ))
    shared_donors.sort(key=lambda d: sum(d.amounts.values()), reverse=True)

    return ComparisonResponse(
        rep_ids=[rep.id for rep in reps],
        reps=rep_profiles,
        shared_donors=shared_donors[:20],
    )


# ── CSV Export ─────────────────────────────────────────────────────────────────


@router.get("/export/{rep_id}.csv", summary="Export representative data as CSV")
def export_csv(rep_id: str, db: Session = Depends(get_db)):
    """
    Download a representative's funding, alignment scores, and voting record as CSV.

    The file is structured in labelled sections (representative, donor, alignment_score, vote)
    so it can be loaded into Excel or pandas with a simple filter on the first column.
    """
    from adapters.postgres.orm_models import AlignmentScoreRow

    rep = db.get(CanonicalRepRow, rep_id)
    if rep is None:
        raise HTTPException(status_code=404, detail="Representative not found")

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(["# Follow the Money — Representative Export"])
    writer.writerow(["# Data sourced from FEC filings. Correlation ≠ causation."])
    writer.writerow(["# https://follow-the-money.example.com/docs/methodology"])
    writer.writerow([])

    # Representative
    writer.writerow(["section", "id", "full_name", "party", "chamber", "state", "district", "bioguide_id"])
    writer.writerow([
        "representative", rep.id, rep.full_name, rep.party,
        rep.chamber, rep.state, rep.district or "", rep.bioguide_id or "",
    ])

    # Donors
    donor_rows = db.execute(
        text("""
            SELECT r.donor_id, cd.name, cd.donor_type, cd.industry,
                   SUM(r.total_amount_cents) AS total_cents
            FROM canonical_donor_rep_relationships r
            JOIN canonical_donors cd ON cd.id = r.donor_id
            WHERE r.rep_id = :rid
            GROUP BY r.donor_id, cd.name, cd.donor_type, cd.industry
            ORDER BY total_cents DESC
            LIMIT 50
        """),
        {"rid": rep_id},
    ).fetchall()
    if donor_rows:
        writer.writerow([])
        writer.writerow(["section", "donor_id", "donor_name", "donor_type", "industry", "total_cents"])
        for row in donor_rows:
            writer.writerow(["donor", row[0], row[1], row[2], row[3] or "", int(row[4])])

    # Alignment scores
    score_rows = (
        db.query(AlignmentScoreRow)
        .filter_by(rep_id=rep_id)
        .order_by(AlignmentScoreRow.shift.desc())
        .all()
    )
    if score_rows:
        writer.writerow([])
        writer.writerow([
            "section", "industry", "score", "confidence", "evidence_count",
            "before_score", "after_score", "shift", "p_value",
        ])
        for s in score_rows:
            writer.writerow([
                "alignment_score", s.industry, s.score, s.confidence,
                s.evidence_count, s.before_score, s.after_score, s.shift, s.p_value,
            ])

    # Voting record
    if rep.bioguide_id:
        vote_rows = db.execute(
            text("""
                SELECT rv.bill_id, rv.bill_title, rv.position,
                       rv.voted_at, rv.chamber, b.industries
                FROM raw_votes rv
                LEFT JOIN bills b ON b.congress_gov_id = rv.bill_id
                WHERE rv.member_bioguide_id = :bioguide_id
                ORDER BY rv.voted_at DESC
                LIMIT 200
            """),
            {"bioguide_id": rep.bioguide_id},
        ).fetchall()
        if vote_rows:
            writer.writerow([])
            writer.writerow(["section", "bill_id", "bill_title", "position", "voted_at", "chamber", "industries"])
            for row in vote_rows:
                try:
                    industries = ",".join(json.loads(row[5] or "[]"))
                except (json.JSONDecodeError, TypeError):
                    industries = ""
                writer.writerow([
                    "vote",
                    row[0] or "", row[1] or "",
                    _POSITION_NORM.get(str(row[2]), str(row[2]).lower()),
                    str(row[3])[:10] if row[3] else "",
                    str(row[4] or "").lower(),
                    industries,
                ])

    output.seek(0)
    safe_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in rep.full_name)
    filename = f"{safe_name}_{rep.id}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Platform stats ─────────────────────────────────────────────────────────────


@router.get("/stats", response_model=PlatformStats, summary="Platform-wide aggregate stats")
def get_stats(db: Session = Depends(get_db)):
    """Live counts of representatives, donors, total raised, and correlations."""
    from adapters.postgres.orm_models import AlignmentScoreRow

    total_reps = int(db.execute(text("SELECT COUNT(*) FROM canonical_reps")).scalar() or 0)
    total_donors = int(db.execute(text("SELECT COUNT(*) FROM canonical_donors")).scalar() or 0)
    total_raised_cents = int(
        db.execute(text("SELECT COALESCE(SUM(total_amount_cents), 0) FROM canonical_donor_rep_relationships")).scalar() or 0
    )
    total_correlations = int(db.execute(text("SELECT COUNT(*) FROM alignment_scores")).scalar() or 0)

    return PlatformStats(
        total_reps=total_reps,
        total_donors=total_donors,
        total_raised_cents=total_raised_cents,
        total_correlations=total_correlations,
    )


# ── Activity ticker ─────────────────────────────────────────────────────────────


@router.get("/ticker", response_model=list[TickerItem], summary="Recent FEC filing activity")
def get_ticker(limit: int = 20, db: Session = Depends(get_db)):
    """Latest individual FEC contribution filings, ordered by ingestion time."""
    limit = min(limit, 100)
    rows = db.execute(
        text("""
            SELECT contributor_name, amount_cents, committee_id, contribution_date
            FROM raw_filings
            WHERE contributor_name IS NOT NULL AND amount_cents > 0
            ORDER BY fetched_at DESC, contribution_date DESC
            LIMIT :limit
        """),
        {"limit": limit},
    ).fetchall()

    return [
        TickerItem(
            contributor_name=str(row[0]),
            amount_cents=int(row[1]),
            committee_id=str(row[2] or ""),
            contribution_date=str(row[3])[:10] if row[3] else None,
        )
        for row in rows
    ]


# ── JSON Export ─────────────────────────────────────────────────────────────────


@router.get("/export/{rep_id}.json", summary="Export representative data as JSON")
def export_json(rep_id: str, db: Session = Depends(get_db)):
    """
    Download a representative's funding, alignment scores, and voting record as JSON.

    Same data as the CSV export, structured as a JSON object with sections
    ``representative``, ``donors``, ``alignment_scores``, and ``votes``.
    """
    from adapters.postgres.orm_models import AlignmentScoreRow

    rep = db.get(CanonicalRepRow, rep_id)
    if rep is None:
        raise HTTPException(status_code=404, detail="Representative not found")

    donor_rows = db.execute(
        text("""
            SELECT r.donor_id, cd.name, cd.donor_type, cd.industry,
                   SUM(r.total_amount_cents) AS total_cents
            FROM canonical_donor_rep_relationships r
            JOIN canonical_donors cd ON cd.id = r.donor_id
            WHERE r.rep_id = :rid
            GROUP BY r.donor_id, cd.name, cd.donor_type, cd.industry
            ORDER BY total_cents DESC
            LIMIT 50
        """),
        {"rid": rep_id},
    ).fetchall()

    score_rows = (
        db.query(AlignmentScoreRow)
        .filter_by(rep_id=rep_id)
        .order_by(AlignmentScoreRow.shift.desc())
        .all()
    )

    vote_rows = []
    if rep.bioguide_id:
        vote_rows = db.execute(
            text("""
                SELECT rv.bill_id, rv.bill_title, rv.position,
                       rv.voted_at, rv.chamber, b.industries
                FROM raw_votes rv
                LEFT JOIN bills b ON b.congress_gov_id = rv.bill_id
                WHERE rv.member_bioguide_id = :bioguide_id
                ORDER BY rv.voted_at DESC
                LIMIT 200
            """),
            {"bioguide_id": rep.bioguide_id},
        ).fetchall()

    payload = {
        "meta": {
            "source": "FEC filings + Congress.gov",
            "disclaimer": "Correlation ≠ causation. See /docs/methodology.",
        },
        "representative": {
            "id": rep.id,
            "full_name": rep.full_name,
            "party": rep.party,
            "chamber": rep.chamber,
            "state": rep.state,
            "district": rep.district,
            "bioguide_id": rep.bioguide_id,
        },
        "donors": [
            {
                "donor_id": row[0],
                "donor_name": row[1],
                "donor_type": row[2],
                "industry": row[3],
                "total_cents": int(row[4]),
            }
            for row in donor_rows
        ],
        "alignment_scores": [
            {
                "industry": s.industry,
                "score": s.score,
                "confidence": s.confidence,
                "evidence_count": s.evidence_count,
                "before_score": s.before_score,
                "after_score": s.after_score,
                "shift": s.shift,
                "p_value": s.p_value,
            }
            for s in score_rows
        ],
        "votes": [
            {
                "bill_id": str(row[0] or ""),
                "bill_title": str(row[1] or ""),
                "position": _POSITION_NORM.get(str(row[2]), str(row[2]).lower()),
                "voted_at": str(row[3])[:10] if row[3] else "",
                "chamber": str(row[4] or "").lower(),
                "industries": _safe_json(row[5]),
            }
            for row in vote_rows
        ],
    }

    safe_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in rep.full_name)
    filename = f"{safe_name}_{rep.id}.json"
    return StreamingResponse(
        iter([json.dumps(payload, indent=2)]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _safe_json(value) -> list:
    try:
        return json.loads(value or "[]")
    except (json.JSONDecodeError, TypeError):
        return []


# ── Embeddable widget ──────────────────────────────────────────────────────────


@router.get("/widget/{rep_id}", response_class=HTMLResponse, summary="Embeddable funding summary widget")
def widget(rep_id: str, theme: str = "light", db: Session = Depends(get_db)):
    """
    Returns a self-contained HTML card for embedding on third-party sites.

    Usage: ``<iframe src="/v1/widget/{rep_id}" width="340" height="220" frameborder="0"></iframe>``

    Optional ``?theme=dark`` for a dark card.
    """
    rep = db.get(CanonicalRepRow, rep_id)
    if rep is None:
        raise HTTPException(status_code=404, detail="Representative not found")

    total_cents = int(
        db.execute(
            text("SELECT COALESCE(SUM(total_amount_cents),0) "
                 "FROM canonical_donor_rep_relationships WHERE rep_id=:rid"),
            {"rid": rep_id},
        ).scalar() or 0
    )
    top_industry_rows = db.execute(
        text("""
            SELECT cd.industry, SUM(r.total_amount_cents) AS tc
            FROM canonical_donor_rep_relationships r
            JOIN canonical_donors cd ON cd.id = r.donor_id
            WHERE r.rep_id = :rid AND cd.industry IS NOT NULL
            GROUP BY cd.industry ORDER BY tc DESC LIMIT 3
        """),
        {"rid": rep_id},
    ).fetchall()

    is_dark = theme.lower() == "dark"
    bg    = "#1a1a2e" if is_dark else "#ffffff"
    fg    = "#e0e0e0" if is_dark else "#1a1a1a"
    muted = "#888"    if is_dark else "#6b7280"
    party_color = "#1A4FD6" if rep.party == "D" else ("#E63022" if rep.party == "R" else "#6b7280")

    def _fmt(cents: int) -> str:
        d = cents / 100
        if d >= 1_000_000: return f"${d/1_000_000:.1f}M"
        if d >= 1_000:     return f"${d/1_000:.0f}K"
        return f"${d:.0f}"

    industry_rows_html = "".join(
        f'<li style="display:flex;justify-content:space-between;font-size:11px;margin-top:4px">'
        f'<span style="color:{muted};text-transform:capitalize">{row[0].replace("_"," ")}</span>'
        f'<span style="font-weight:600">{_fmt(int(row[1]))}</span></li>'
        for row in top_industry_rows
    )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>*{{box-sizing:border-box;margin:0;padding:0;font-family:system-ui,sans-serif}}</style>
</head>
<body style="background:{bg};color:{fg};padding:16px;border-radius:8px">
  <div style="border-left:4px solid {party_color};padding-left:12px;margin-bottom:12px">
    <div style="font-weight:700;font-size:15px">{rep.full_name}</div>
    <div style="font-size:11px;color:{muted};margin-top:2px">
      {"House" if rep.chamber=="house" else "Senate"} · {rep.state}
      {" · " + rep.district if rep.district else ""}
    </div>
  </div>
  <div style="font-size:12px;color:{muted}">Total raised</div>
  <div style="font-size:22px;font-weight:700;margin:2px 0 10px">{_fmt(total_cents)}</div>
  <ul style="list-style:none">{industry_rows_html}</ul>
  <div style="margin-top:12px;font-size:10px;color:{muted}">
    Data: FEC filings · <a href="https://follow-the-money.example.com/rep/{rep_id}"
    style="color:{muted}" target="_blank">Follow the Money</a>
  </div>
</body></html>"""

    return HTMLResponse(content=html)
