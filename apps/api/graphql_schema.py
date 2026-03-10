"""
Strawberry GraphQL schema — Sprint 6.

Types:     RepProfileGQL, DonorProfileGQL, NetworkNodeGQL, NetworkEdgeGQL, NetworkGraphGQL
Queries:   representative, donor, repNetwork, donorNetwork, hello
"""

from __future__ import annotations

from typing import Optional

import strawberry
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from strawberry.fastapi import GraphQLRouter

from adapters.postgres.orm_models import CanonicalDonorRow, CanonicalRepRow
from infrastructure.database import get_db


# ── GraphQL types ──────────────────────────────────────────────────────────────


@strawberry.type
class IndustrySummaryGQL:
    industry: str
    total_cents: int


@strawberry.type
class TopDonorGQL:
    donor_id: str
    donor_name: str
    total_cents: int
    donor_type: str


@strawberry.type
class RepProfileGQL:
    id: str
    full_name: str
    party: str
    chamber: str
    state: str
    district: Optional[str]
    bioguide_id: Optional[str]
    total_raised_cents: int
    top_industries: list[IndustrySummaryGQL]
    top_donors: list[TopDonorGQL]


@strawberry.type
class DonorProfileGQL:
    id: str
    name: str
    donor_type: str
    industry: Optional[str]
    state: Optional[str]
    total_given_cents: int


@strawberry.type
class NetworkNodeGQL:
    id: str
    node_type: str          # "rep" or "donor"
    label: str
    party: Optional[str]    # set for reps
    chamber: Optional[str]
    state: Optional[str]
    donor_type: Optional[str]  # set for donors
    is_center: bool


@strawberry.type
class NetworkEdgeGQL:
    source: str
    target: str
    total_cents: int
    cycles: list[int]


@strawberry.type
class NetworkGraphGQL:
    nodes: list[NetworkNodeGQL]
    edges: list[NetworkEdgeGQL]


# ── Helpers ────────────────────────────────────────────────────────────────────


def _rep_profile(rep: CanonicalRepRow, db: Session) -> RepProfileGQL:
    total = int(
        db.execute(
            text(
                "SELECT COALESCE(SUM(total_amount_cents),0) "
                "FROM canonical_donor_rep_relationships WHERE rep_id=:id"
            ),
            {"id": rep.id},
        ).scalar()
        or 0
    )
    industry_rows = db.execute(
        text("""
            SELECT cd.industry, SUM(r.total_amount_cents) AS cents
            FROM canonical_donor_rep_relationships r
            JOIN canonical_donors cd ON cd.id = r.donor_id
            WHERE r.rep_id = :id AND cd.industry IS NOT NULL
            GROUP BY cd.industry ORDER BY cents DESC LIMIT 10
        """),
        {"id": rep.id},
    ).fetchall()
    donor_rows = db.execute(
        text("""
            SELECT r.donor_id, cd.name, cd.donor_type, SUM(r.total_amount_cents) AS cents
            FROM canonical_donor_rep_relationships r
            JOIN canonical_donors cd ON cd.id = r.donor_id
            WHERE r.rep_id = :id
            GROUP BY r.donor_id, cd.name, cd.donor_type
            ORDER BY cents DESC LIMIT 10
        """),
        {"id": rep.id},
    ).fetchall()
    return RepProfileGQL(
        id=rep.id,
        full_name=rep.full_name,
        party=rep.party,
        chamber=rep.chamber,
        state=rep.state,
        district=rep.district,
        bioguide_id=rep.bioguide_id,
        total_raised_cents=total,
        top_industries=[IndustrySummaryGQL(industry=r[0], total_cents=int(r[1])) for r in industry_rows],
        top_donors=[
            TopDonorGQL(donor_id=r[0], donor_name=r[1], donor_type=r[2], total_cents=int(r[3]))
            for r in donor_rows
        ],
    )


def _network_to_gql(data: dict) -> NetworkGraphGQL:
    return NetworkGraphGQL(
        nodes=[
            NetworkNodeGQL(
                id=n["id"],
                node_type=n["type"],
                label=n["label"],
                party=n.get("party"),
                chamber=n.get("chamber"),
                state=n.get("state"),
                donor_type=n.get("donor_type"),
                is_center=n.get("is_center", False),
            )
            for n in data["nodes"]
        ],
        edges=[
            NetworkEdgeGQL(
                source=e["source"],
                target=e["target"],
                total_cents=e["total_cents"],
                cycles=e.get("cycles") or [],
            )
            for e in data["edges"]
        ],
    )


# ── Query root ─────────────────────────────────────────────────────────────────


@strawberry.type
class Query:
    @strawberry.field(description="API health check")
    def hello(self) -> str:
        return "Follow the Money GraphQL API — v0.1.0"

    @strawberry.field(description="Full representative profile with funding summary")
    def representative(self, id: str, info: strawberry.types.Info) -> Optional[RepProfileGQL]:
        db: Session = info.context["db"]
        rep = db.get(CanonicalRepRow, id)
        if rep is None:
            return None
        return _rep_profile(rep, db)

    @strawberry.field(description="Donor profile with total giving")
    def donor(self, id: str, info: strawberry.types.Info) -> Optional[DonorProfileGQL]:
        db: Session = info.context["db"]
        donor = db.get(CanonicalDonorRow, id)
        if donor is None:
            return None
        total = int(
            db.execute(
                text(
                    "SELECT COALESCE(SUM(total_amount_cents),0) "
                    "FROM canonical_donor_rep_relationships WHERE donor_id=:id"
                ),
                {"id": id},
            ).scalar()
            or 0
        )
        return DonorProfileGQL(
            id=donor.id,
            name=donor.name,
            donor_type=donor.donor_type,
            industry=donor.industry,
            state=donor.state,
            total_given_cents=total,
        )

    @strawberry.field(description="Rep funding network — donors (hop-1) + sibling reps (hop-2)")
    def rep_network(self, rep_id: str, limit: int = 15) -> NetworkGraphGQL:
        try:
            from adapters.neo4j.network_query import NetworkQueryService
            data = NetworkQueryService().get_rep_network(rep_id, direct_limit=limit)
        except Exception:
            data = {"nodes": [], "edges": []}
        return _network_to_gql(data)

    @strawberry.field(description="Donor funding network — reps (hop-1) + sibling donors (hop-2)")
    def donor_network(self, donor_id: str, limit: int = 15) -> NetworkGraphGQL:
        try:
            from adapters.neo4j.network_query import NetworkQueryService
            data = NetworkQueryService().get_donor_network(donor_id, direct_limit=limit)
        except Exception:
            data = {"nodes": [], "edges": []}
        return _network_to_gql(data)


# ── App assembly ───────────────────────────────────────────────────────────────


async def _get_context(db: Session = Depends(get_db)) -> dict:
    return {"db": db}


schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(schema, context_getter=_get_context)
