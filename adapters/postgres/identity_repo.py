"""
PostgreSQL implementation of IdentityRepository.

Reads from raw_filings/raw_votes (via ingestion tables) and writes to
canonical_reps, canonical_donors, and lis_bioguide_map.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from adapters.postgres.orm_models import (
    CanonicalDonorRow,
    CanonicalRepRow,
    LisBioguideMapRow,
)
from domain.identity.models import (
    CanonicalDonor,
    CanonicalRep,
    Chamber,
    DonorId,
    DonorType,
    Party,
    RepId,
)
from domain.identity.ports import IdentityRepository


class PostgresIdentityRepository(IdentityRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Reps ─────────────────────────────────────────────────────────────────

    def get_rep(self, rep_id: RepId) -> CanonicalRep | None:
        row = self._session.get(CanonicalRepRow, str(rep_id))
        return _rep_from_row(row) if row else None

    def save_rep(self, rep: CanonicalRep) -> None:
        row = self._session.get(CanonicalRepRow, str(rep.id))
        if row is None:
            row = CanonicalRepRow(id=str(rep.id))
            self._session.add(row)
        row.full_name = rep.full_name
        row.party = rep.party.value
        row.chamber = rep.chamber.value
        row.state = rep.state
        row.district = rep.district
        row.bioguide_id = rep.bioguide_id
        row.fec_candidate_id = rep.fec_candidate_id
        self._session.flush()

    def find_rep_by_bioguide_id(self, bioguide_id: str) -> CanonicalRep | None:
        row = (
            self._session.query(CanonicalRepRow)
            .filter_by(bioguide_id=bioguide_id)
            .first()
        )
        return _rep_from_row(row) if row else None

    def find_rep_by_fec_id(self, fec_id: str) -> CanonicalRep | None:
        row = (
            self._session.query(CanonicalRepRow)
            .filter_by(fec_candidate_id=fec_id)
            .first()
        )
        return _rep_from_row(row) if row else None

    def find_rep_by_lis_id(self, lis_member_id: str) -> CanonicalRep | None:
        mapping = self._session.get(LisBioguideMapRow, lis_member_id)
        if mapping is None:
            return None
        return self.find_rep_by_bioguide_id(mapping.bioguide_id)

    def save_lis_bioguide_mapping(
        self, lis_member_id: str, bioguide_id: str, full_name: str, state: str, party: str
    ) -> None:
        existing = self._session.get(LisBioguideMapRow, lis_member_id)
        if existing is None:
            self._session.add(LisBioguideMapRow(
                lis_member_id=lis_member_id,
                bioguide_id=bioguide_id,
                full_name=full_name,
                state=state,
                party=party,
            ))
            self._session.flush()

    # ── Donors ────────────────────────────────────────────────────────────────

    def get_donor(self, donor_id: DonorId) -> CanonicalDonor | None:
        row = self._session.get(CanonicalDonorRow, str(donor_id))
        return _donor_from_row(row) if row else None

    def save_donor(self, donor: CanonicalDonor) -> None:
        row = self._session.get(CanonicalDonorRow, str(donor.id))
        if row is None:
            row = CanonicalDonorRow(id=str(donor.id))
            self._session.add(row)
        row.name = donor.name
        row.donor_type = donor.donor_type.value
        row.industry = donor.industry.value if donor.industry else None
        row.state = donor.state
        row.fec_ids = json.dumps(donor.fec_ids)
        self._session.flush()

    def find_donor_by_fec_id(self, fec_id: str) -> CanonicalDonor | None:
        # fec_ids is stored as a JSON array — search with LIKE for simplicity.
        # Sprint 4 can add a proper join table if performance requires it.
        rows = self._session.query(CanonicalDonorRow).all()
        for row in rows:
            if fec_id in json.loads(row.fec_ids or "[]"):
                return _donor_from_row(row)
        return None


# ── Row → domain model mappers ────────────────────────────────────────────────


def _rep_from_row(row: CanonicalRepRow) -> CanonicalRep:
    return CanonicalRep(
        id=RepId(row.id),
        full_name=row.full_name,
        party=Party(row.party),
        chamber=Chamber(row.chamber),
        state=row.state,
        district=row.district,
        bioguide_id=row.bioguide_id,
        fec_candidate_id=row.fec_candidate_id,
    )


def _donor_from_row(row: CanonicalDonorRow) -> CanonicalDonor:
    return CanonicalDonor(
        id=DonorId(row.id),
        name=row.name,
        donor_type=DonorType(row.donor_type),
        industry=None,   # re-hydrated in Sprint 7 when NLP runs
        state=row.state,
        fec_ids=json.loads(row.fec_ids or "[]"),
    )
