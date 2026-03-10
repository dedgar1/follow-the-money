"""
Public REST API router — all endpoints from CLAUDE.md spec.

All endpoints return 501 in Sprint 1. Implemented progressively in Sprints 4–9.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["public"])

_not_implemented = JSONResponse(
    status_code=501,
    content={"detail": "Not yet implemented — see sprint roadmap"},
)


@router.get("/representatives", summary="List representatives")
def list_representatives(state: str | None = None, chamber: str | None = None, party: str | None = None):
    """TODO Sprint 4: Filter by state, chamber, party."""
    return _not_implemented


@router.get("/representatives/{rep_id}", summary="Get representative profile")
def get_representative(rep_id: str):
    """TODO Sprint 4: Full rep profile with funding summary."""
    return _not_implemented


@router.get("/representatives/{rep_id}/votes", summary="Get voting record")
def get_representative_votes(rep_id: str):
    """TODO Sprint 7: Voting record with industry tags."""
    return _not_implemented


@router.get("/representatives/{rep_id}/correlations", summary="Get alignment scores")
def get_representative_correlations(rep_id: str):
    """TODO Sprint 8: AlignmentScore list with shift and confidence."""
    return _not_implemented


@router.get("/donors/{donor_id}", summary="Get donor profile")
def get_donor(donor_id: str):
    """TODO Sprint 4: Donor profile with recipients."""
    return _not_implemented


@router.get("/donors/{donor_id}/recipients", summary="List reps funded by donor")
def get_donor_recipients(donor_id: str):
    """TODO Sprint 4: All reps funded by this donor."""
    return _not_implemented


@router.get("/search", summary="Search representatives and donors")
def search(q: str):
    """TODO Sprint 5: Name search across reps and donors."""
    return _not_implemented


@router.get("/zip/{zipcode}", summary="Get reps for ZIP code")
def zip_lookup(zipcode: str):
    """TODO Sprint 5: ZIP → district → representatives."""
    return _not_implemented


@router.get("/compare", summary="Side-by-side representative comparison")
def compare(ids: str):
    """TODO Sprint 9: Comma-separated rep IDs → comparison report."""
    return _not_implemented


@router.get("/export/{rep_id}.csv", summary="Export representative data as CSV")
def export_csv(rep_id: str):
    """TODO Sprint 9: CSV export of rep funding data."""
    return _not_implemented
