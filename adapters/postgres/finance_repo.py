"""
PostgreSQL implementation of FinanceRepository and FundingQueryPort.

Reads from canonical_donor_rep_relationships (aggregate root written by
aggregate_finance pipeline task). Also provides FundingQueryPort for
the GraphQL / REST layers.
"""

from __future__ import annotations

import json
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from adapters.postgres.orm_models import CanonicalRelationshipRow
from domain.finance.models import (
    DonorRepRelationship,
    RelationshipId,
)
from domain.finance.ports import FinanceRepository, FundingQueryPort
from domain.identity.models import (
    CanonicalDonorRef,
    CanonicalRepRef,
    DonorId,
    RepId,
)
from domain.shared.election_cycle import ElectionCycle
from domain.shared.money import Money


class PostgresFinanceRepository(FinanceRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_relationship(self, rel_id: RelationshipId) -> DonorRepRelationship | None:
        row = self._session.get(CanonicalRelationshipRow, str(rel_id))
        return _relationship_from_row(row) if row else None

    def save_relationship(self, rel: DonorRepRelationship) -> None:
        row = self._session.get(CanonicalRelationshipRow, str(rel.id))
        if row is None:
            row = CanonicalRelationshipRow(id=str(rel.id))
            self._session.add(row)
        row.donor_id = str(rel.donor.id)
        row.rep_id = str(rel.representative.id)
        row.total_amount_cents = rel.total_amount.cents
        row.contribution_count = len(rel.contributions)
        row.first_donation_date = rel.first_donation.isoformat() if rel.first_donation else None
        row.latest_donation_date = rel.latest_donation.isoformat() if rel.latest_donation else None
        row.election_cycles = json.dumps([c.year for c in rel.cycles])
        self._session.flush()

    def find_relationships_for_rep(
        self, rep_id: RepId, cycle: ElectionCycle | None = None
    ) -> list[DonorRepRelationship]:
        rows = self._session.query(CanonicalRelationshipRow).filter_by(rep_id=str(rep_id)).all()
        relationships = [_relationship_from_row(r) for r in rows]
        if cycle is not None:
            relationships = [
                r for r in relationships if any(c.year == cycle.year for c in r.cycles)
            ]
        return relationships

    def find_relationships_for_donor(
        self, donor_id: DonorId
    ) -> list[DonorRepRelationship]:
        rows = (
            self._session.query(CanonicalRelationshipRow)
            .filter_by(donor_id=str(donor_id))
            .all()
        )
        return [_relationship_from_row(r) for r in rows]


class PostgresFundingQueryPort(FundingQueryPort):
    """Read-optimised query port for the API layer."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_top_donors(
        self, rep_id: RepId, cycle: ElectionCycle, limit: int = 10
    ) -> list[DonorRepRelationship]:
        rows = (
            self._session.query(CanonicalRelationshipRow)
            .filter(CanonicalRelationshipRow.rep_id == str(rep_id))
            .order_by(CanonicalRelationshipRow.total_amount_cents.desc())
            .limit(limit * 3)  # over-fetch to account for cycle filtering
            .all()
        )
        result = []
        for row in rows:
            cycles = json.loads(row.election_cycles or "[]")
            if cycle.year in cycles:
                result.append(_relationship_from_row(row))
            if len(result) >= limit:
                break
        return result

    def get_top_industries(self, rep_id: RepId, cycle: ElectionCycle) -> list[dict]:
        """
        Returns a list of {"industry": str, "total_cents": int} dicts sorted descending.
        Joins canonical_donors to aggregate by industry. Returns empty list if no data.
        """
        sql = text("""
            SELECT
                cd.industry,
                SUM(r.total_amount_cents) AS total_cents
            FROM canonical_donor_rep_relationships r
            JOIN canonical_donors cd ON cd.id = r.donor_id
            WHERE r.rep_id = :rep_id
              AND r.election_cycles::jsonb @> :cycle_json::jsonb
              AND cd.industry IS NOT NULL
            GROUP BY cd.industry
            ORDER BY total_cents DESC
        """)
        rows = self._session.execute(
            sql,
            {"rep_id": str(rep_id), "cycle_json": json.dumps([cycle.year])},
        ).fetchall()
        return [{"industry": row[0], "total_cents": row[1]} for row in rows]


# ── Row → domain model mapper ─────────────────────────────────────────────────


def _parse_date(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def _relationship_from_row(row: CanonicalRelationshipRow) -> DonorRepRelationship:
    cycles_raw: list[int] = json.loads(row.election_cycles or "[]")
    return DonorRepRelationship(
        id=RelationshipId(row.id),
        donor=CanonicalDonorRef(id=DonorId(row.donor_id), name=""),
        representative=CanonicalRepRef(id=RepId(row.rep_id), full_name=""),
        first_donation=_parse_date(row.first_donation_date),
        latest_donation=_parse_date(row.latest_donation_date),
        total_amount=Money(cents=row.total_amount_cents),
        cycles=[ElectionCycle(year=y) for y in cycles_raw],
    )
