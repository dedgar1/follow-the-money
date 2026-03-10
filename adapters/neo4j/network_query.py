"""
Multi-hop Neo4j graph traversal for the donor-rep funding network.

Graph schema:
  (:CanonicalDonor)-[:FUNDED]->(:CanonicalRep)

Sprint 6 queries:
  - get_donor_network  — donor + funded reps + other donors at those reps (2-hop)
  - get_rep_network    — rep + their donors + other reps those donors funded (2-hop)
"""

from __future__ import annotations

from infrastructure.neo4j_driver import get_driver


class NetworkQueryService:
    """Multi-hop graph traversal returning {nodes, edges} dicts for D3."""

    # ── Donor-centred network ──────────────────────────────────────────────────

    def get_donor_network(
        self,
        donor_id: str,
        direct_limit: int = 15,
        hop2_limit: int = 10,
    ) -> dict:
        """
        Centred on one donor:
          hop-1 → reps funded by this donor (sorted by amount desc)
          hop-2 → other donors who also funded those same reps
        """
        driver = get_driver()

        with driver.session() as session:
            center = session.run(
                "MATCH (d:CanonicalDonor {id: $id}) "
                "RETURN d.id AS id, d.name AS label, d.donor_type AS donor_type",
                id=donor_id,
            ).single()

            if not center:
                return {"nodes": [], "edges": []}

            rep_rows = session.run(
                """
                MATCH (d:CanonicalDonor {id: $donor_id})-[f:FUNDED]->(r:CanonicalRep)
                RETURN r.id AS id, r.full_name AS label, r.party AS party,
                       r.chamber AS chamber, r.state AS state,
                       f.total_cents AS total_cents, f.cycles AS cycles
                ORDER BY f.total_cents DESC
                LIMIT $limit
                """,
                donor_id=donor_id,
                limit=direct_limit,
            ).data()

            rep_ids = [r["id"] for r in rep_rows]

            hop2_rows = []
            if rep_ids:
                hop2_rows = session.run(
                    """
                    MATCH (d2:CanonicalDonor)-[f:FUNDED]->(r:CanonicalRep)
                    WHERE r.id IN $rep_ids AND d2.id <> $donor_id
                    RETURN DISTINCT d2.id AS id, d2.name AS label,
                           d2.donor_type AS donor_type,
                           r.id AS rep_id,
                           f.total_cents AS total_cents, f.cycles AS cycles
                    ORDER BY f.total_cents DESC
                    LIMIT $limit
                    """,
                    rep_ids=rep_ids,
                    donor_id=donor_id,
                    limit=hop2_limit,
                ).data()

        return _build_graph(
            center_node={
                "id": donor_id,
                "type": "donor",
                "label": center["label"],
                "donor_type": center["donor_type"],
                "is_center": True,
            },
            hop1_nodes=[
                {
                    "id": r["id"],
                    "type": "rep",
                    "label": r["label"],
                    "party": r["party"],
                    "chamber": r["chamber"],
                    "state": r["state"],
                    "is_center": False,
                }
                for r in rep_rows
            ],
            hop1_edges=[
                {
                    "source": donor_id,
                    "target": r["id"],
                    "total_cents": r["total_cents"],
                    "cycles": r["cycles"] or [],
                }
                for r in rep_rows
            ],
            hop2_nodes=[
                {
                    "id": h["id"],
                    "type": "donor",
                    "label": h["label"],
                    "donor_type": h["donor_type"],
                    "is_center": False,
                }
                for h in hop2_rows
            ],
            hop2_edges=[
                {
                    "source": h["id"],
                    "target": h["rep_id"],
                    "total_cents": h["total_cents"],
                    "cycles": h["cycles"] or [],
                }
                for h in hop2_rows
            ],
        )

    # ── Rep-centred network ───────────────────────────────────────────────────

    def get_rep_network(
        self,
        rep_id: str,
        direct_limit: int = 15,
        hop2_limit: int = 10,
    ) -> dict:
        """
        Centred on one rep:
          hop-1 → donors who funded this rep (sorted by amount desc)
          hop-2 → other reps funded by those same donors
        """
        driver = get_driver()

        with driver.session() as session:
            center = session.run(
                "MATCH (r:CanonicalRep {id: $id}) "
                "RETURN r.id AS id, r.full_name AS label, r.party AS party, "
                "r.chamber AS chamber, r.state AS state",
                id=rep_id,
            ).single()

            if not center:
                return {"nodes": [], "edges": []}

            donor_rows = session.run(
                """
                MATCH (d:CanonicalDonor)-[f:FUNDED]->(r:CanonicalRep {id: $rep_id})
                RETURN d.id AS id, d.name AS label, d.donor_type AS donor_type,
                       f.total_cents AS total_cents, f.cycles AS cycles
                ORDER BY f.total_cents DESC
                LIMIT $limit
                """,
                rep_id=rep_id,
                limit=direct_limit,
            ).data()

            donor_ids = [d["id"] for d in donor_rows]

            hop2_rows = []
            if donor_ids:
                hop2_rows = session.run(
                    """
                    MATCH (d:CanonicalDonor)-[f:FUNDED]->(r2:CanonicalRep)
                    WHERE d.id IN $donor_ids AND r2.id <> $rep_id
                    RETURN DISTINCT r2.id AS id, r2.full_name AS label,
                           r2.party AS party, r2.chamber AS chamber, r2.state AS state,
                           d.id AS donor_id,
                           f.total_cents AS total_cents, f.cycles AS cycles
                    ORDER BY f.total_cents DESC
                    LIMIT $limit
                    """,
                    donor_ids=donor_ids,
                    rep_id=rep_id,
                    limit=hop2_limit,
                ).data()

        return _build_graph(
            center_node={
                "id": rep_id,
                "type": "rep",
                "label": center["label"],
                "party": center["party"],
                "chamber": center["chamber"],
                "state": center["state"],
                "is_center": True,
            },
            hop1_nodes=[
                {
                    "id": d["id"],
                    "type": "donor",
                    "label": d["label"],
                    "donor_type": d["donor_type"],
                    "is_center": False,
                }
                for d in donor_rows
            ],
            hop1_edges=[
                {
                    "source": d["id"],
                    "target": rep_id,
                    "total_cents": d["total_cents"],
                    "cycles": d["cycles"] or [],
                }
                for d in donor_rows
            ],
            hop2_nodes=[
                {
                    "id": h["id"],
                    "type": "rep",
                    "label": h["label"],
                    "party": h["party"],
                    "chamber": h["chamber"],
                    "state": h["state"],
                    "is_center": False,
                }
                for h in hop2_rows
            ],
            hop2_edges=[
                {
                    "source": h["donor_id"],
                    "target": h["id"],
                    "total_cents": h["total_cents"],
                    "cycles": h["cycles"] or [],
                }
                for h in hop2_rows
            ],
        )


# ── Graph builder (pure function, easily testable) ─────────────────────────────


def _build_graph(
    center_node: dict,
    hop1_nodes: list[dict],
    hop1_edges: list[dict],
    hop2_nodes: list[dict],
    hop2_edges: list[dict],
) -> dict:
    """Merge nodes and edges, deduplicate by id / source+target pair."""
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_nodes: set[str] = set()
    seen_edges: set[str] = set()

    def add_node(n: dict) -> None:
        if n["id"] not in seen_nodes:
            nodes.append(n)
            seen_nodes.add(n["id"])

    def add_edge(e: dict) -> None:
        key = f"{e['source']}->{e['target']}"
        if key not in seen_edges:
            edges.append(e)
            seen_edges.add(key)

    add_node(center_node)
    for n in hop1_nodes:
        add_node(n)
    for e in hop1_edges:
        add_edge(e)
    for n in hop2_nodes:
        add_node(n)
    for e in hop2_edges:
        add_edge(e)

    return {"nodes": nodes, "edges": edges}
