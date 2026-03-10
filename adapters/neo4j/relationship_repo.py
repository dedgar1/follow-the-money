"""
Neo4j adapter for donor-representative graph relationships.

Graph schema:
  (:CanonicalDonor {id, name, donor_type})-[:FUNDED {total_cents, cycles, updated_at}]->(:CanonicalRep {id, bioguide_id, full_name, party, chamber, state})

All writes are idempotent MERGE operations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from infrastructure.neo4j_driver import get_driver

logger = logging.getLogger(__name__)


class Neo4jRelationshipRepo:
    """Manages donor → rep FUNDED relationships in the Neo4j graph."""

    def upsert_rep_node(self, rep_id: str, bioguide_id: str | None, full_name: str,
                        party: str, chamber: str, state: str) -> None:
        """Create or update a CanonicalRep node."""
        driver = get_driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (r:CanonicalRep {id: $id})
                SET r.bioguide_id = $bioguide_id,
                    r.full_name   = $full_name,
                    r.party       = $party,
                    r.chamber     = $chamber,
                    r.state       = $state,
                    r.updated_at  = $updated_at
                """,
                id=rep_id,
                bioguide_id=bioguide_id or "",
                full_name=full_name,
                party=party,
                chamber=chamber,
                state=state,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )

    def upsert_donor_node(self, donor_id: str, name: str, donor_type: str) -> None:
        """Create or update a CanonicalDonor node."""
        driver = get_driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (d:CanonicalDonor {id: $id})
                SET d.name       = $name,
                    d.donor_type = $donor_type,
                    d.updated_at = $updated_at
                """,
                id=donor_id,
                name=name,
                donor_type=donor_type,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )

    def upsert_funded_relationship(
        self,
        donor_id: str,
        rep_id: str,
        total_cents: int,
        cycles: list[int],
    ) -> None:
        """
        Create or update the FUNDED edge between a CanonicalDonor and CanonicalRep.

        Uses MERGE to ensure idempotency — safe to call multiple times with
        updated totals.
        """
        driver = get_driver()
        with driver.session() as session:
            session.run(
                """
                MATCH (d:CanonicalDonor {id: $donor_id})
                MATCH (r:CanonicalRep {id: $rep_id})
                MERGE (d)-[f:FUNDED]->(r)
                SET f.total_cents = $total_cents,
                    f.cycles      = $cycles,
                    f.updated_at  = $updated_at
                """,
                donor_id=donor_id,
                rep_id=rep_id,
                total_cents=total_cents,
                cycles=cycles,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )

    def get_relationships_for_rep(self, rep_id: str) -> list[dict]:
        """
        Return all FUNDED edges pointing to a rep.
        Each dict: {donor_id, donor_name, total_cents, cycles}.
        """
        driver = get_driver()
        with driver.session() as session:
            result = session.run(
                """
                MATCH (d:CanonicalDonor)-[f:FUNDED]->(r:CanonicalRep {id: $rep_id})
                RETURN d.id AS donor_id, d.name AS donor_name,
                       f.total_cents AS total_cents, f.cycles AS cycles
                ORDER BY f.total_cents DESC
                """,
                rep_id=rep_id,
            )
            return [dict(record) for record in result]

    def get_relationships_for_donor(self, donor_id: str) -> list[dict]:
        """
        Return all FUNDED edges originating from a donor.
        Each dict: {rep_id, rep_name, total_cents, cycles}.
        """
        driver = get_driver()
        with driver.session() as session:
            result = session.run(
                """
                MATCH (d:CanonicalDonor {id: $donor_id})-[f:FUNDED]->(r:CanonicalRep)
                RETURN r.id AS rep_id, r.full_name AS rep_name,
                       f.total_cents AS total_cents, f.cycles AS cycles
                ORDER BY f.total_cents DESC
                """,
                donor_id=donor_id,
            )
            return [dict(record) for record in result]
