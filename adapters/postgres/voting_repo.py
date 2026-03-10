"""
PostgreSQL adapter for the Voting repository port — Sprint 7.

Reads from raw_votes (via canonical rep bioguide_id) and bills tables.
Writes go to the bills table; raw_votes are written by the ingest_votes pipeline.
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from domain.identity.models import CanonicalRepRef, RepId
from domain.shared.industry import Industry
from domain.voting.models import (
    Bill,
    BillId,
    BillRef,
    RollCallVote,
    Sponsorship,
    VoteId,
    VotePosition,
    VoteType,
)
from domain.voting.ports import VotingRepository


# Maps raw vote strings from Congress.gov / Senate XML → VotePosition
_POSITION_MAP: dict[str, VotePosition] = {
    "Yea": VotePosition.YES,
    "Yes": VotePosition.YES,
    "AYE": VotePosition.YES,
    "Nay": VotePosition.NO,
    "No": VotePosition.NO,
    "NAY": VotePosition.NO,
    "Not Voting": VotePosition.NOT_VOTING,
    "Present": VotePosition.ABSTAIN,
    "Abstain": VotePosition.ABSTAIN,
}


class PostgresVotingRepository(VotingRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── bills ──────────────────────────────────────────────────────────────────

    def get_bill(self, bill_id: BillId) -> Bill | None:
        """Look up a bill by its Congress.gov ID (e.g. 'hr3424')."""
        row = self._db.execute(
            text(
                "SELECT id, title, industries, nlp_confidence, congress, congress_gov_id "
                "FROM bills WHERE congress_gov_id = :cg_id OR id = :id"
            ),
            {"cg_id": str(bill_id), "id": str(bill_id)},
        ).fetchone()
        if row is None:
            return None
        return _bill_from_row(row)

    def save_bill(self, bill: Bill) -> None:
        """Upsert a bill (insert or update industries/confidence on conflict)."""
        from adapters.postgres.orm_models import BillRow
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        industries_json = json.dumps([i.value for i in bill.industries])
        stmt = (
            pg_insert(BillRow)
            .values(
                id=str(bill.id),
                title=bill.title,
                industries=industries_json,
                nlp_confidence=bill.nlp_confidence,
                congress=bill.congress,
                congress_gov_id=bill.congress_gov_id,
            )
            .on_conflict_do_update(
                index_elements=["congress_gov_id"],
                set_={
                    "industries": industries_json,
                    "nlp_confidence": bill.nlp_confidence,
                },
            )
        )
        self._db.execute(stmt)
        self._db.commit()

    # ── votes ──────────────────────────────────────────────────────────────────

    def get_votes_for_rep(
        self,
        rep_id: RepId,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[RollCallVote]:
        """
        Return roll-call votes for a canonical representative.

        Reads from raw_votes via the rep's bioguide_id (the pipeline writes
        votes there); optionally filtered by date range.
        """
        # Resolve canonical rep → bioguide_id
        bioguide_row = self._db.execute(
            text("SELECT bioguide_id FROM canonical_reps WHERE id = :id"),
            {"id": str(rep_id)},
        ).fetchone()
        if bioguide_row is None or bioguide_row[0] is None:
            return []

        bioguide_id = bioguide_row[0]

        clauses = ["rv.member_bioguide_id = :bioguide_id"]
        params: dict = {"bioguide_id": bioguide_id}

        if from_date is not None:
            clauses.append("rv.voted_at >= :from_date")
            params["from_date"] = from_date.strftime("%Y-%m-%d")
        if to_date is not None:
            clauses.append("rv.voted_at <= :to_date")
            params["to_date"] = to_date.strftime("%Y-%m-%d")

        where = " AND ".join(clauses)
        rows = self._db.execute(
            text(f"""
                SELECT rv.id, rv.bill_id, rv.bill_title, rv.position,
                       rv.voted_at, rv.chamber, rv.source_id
                FROM raw_votes rv
                WHERE {where}
                ORDER BY rv.voted_at DESC
                LIMIT 100
            """),
            params,
        ).fetchall()

        return [_vote_from_raw_row(row, rep_id) for row in rows]

    def save_vote(self, vote: RollCallVote) -> None:
        """Not implemented — votes are written by the ingest_votes pipeline."""
        raise NotImplementedError(
            "Votes are written by pipeline.tasks.ingest_votes — use that task."
        )

    def get_sponsorships_for_rep(self, rep_id: RepId) -> list[Sponsorship]:
        """Sponsorship tracking is deferred to Sprint 8."""
        return []


# ── Mapping helpers ────────────────────────────────────────────────────────────


def _bill_from_row(row) -> Bill:
    industries: list[Industry] = []
    try:
        for v in json.loads(row[2] or "[]"):
            try:
                industries.append(Industry(v))
            except ValueError:
                pass
    except (json.JSONDecodeError, TypeError):
        pass

    return Bill(
        id=BillId(row[5] or row[0]),
        title=row[1],
        industries=industries,
        nlp_confidence=float(row[3] or 0.0),
        congress=row[4],
        congress_gov_id=row[5],
    )


def _vote_from_raw_row(row, rep_id: RepId) -> RollCallVote:
    voted_at_str = str(row[4])[:10] if row[4] else ""
    try:
        voted_at = datetime.strptime(voted_at_str, "%Y-%m-%d")
    except ValueError:
        voted_at = datetime.utcnow()

    position = _POSITION_MAP.get(str(row[3]), VotePosition.NOT_VOTING)

    return RollCallVote(
        id=VoteId(str(row[0])),
        bill=BillRef(id=BillId(str(row[1] or "")), title=str(row[2] or "")),
        representative=CanonicalRepRef(id=rep_id, full_name=""),
        position=position,
        voted_at=voted_at,
        vote_type=VoteType.FLOOR,
    )
