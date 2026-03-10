"""
Identity service — entity resolution and canonical lookup.
"""

from __future__ import annotations

from ulid import ULID

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


class EntityResolver:
    """
    Resolves raw donor/rep names to canonical entities.

    Delegates fuzzy matching to the NLP adapter (adapters/nlp/entity_resolver.py).
    This service owns the domain logic: what counts as a canonical entity,
    when to create vs. merge, and how to update the repository.
    """

    def __init__(self, repo: IdentityRepository) -> None:
        self._repo = repo

    def resolve_rep_from_bioguide(
        self,
        bioguide_id: str,
        full_name: str,
        party: str,
        chamber: str,
        state: str,
        district: str | None = None,
        fec_candidate_id: str | None = None,
    ) -> CanonicalRep:
        """
        Upsert a canonical rep by bioguide_id (authoritative Congress.gov identifier).

        If a rep with this bioguide_id already exists, return them.
        Otherwise create a new canonical rep.
        """
        existing = self._repo.find_rep_by_bioguide_id(bioguide_id)
        if existing is not None:
            return existing

        rep = CanonicalRep(
            id=RepId(str(ULID())),
            full_name=full_name,
            party=_parse_party(party),
            chamber=_parse_chamber(chamber),
            state=state.upper()[:2],
            district=district,
            bioguide_id=bioguide_id,
            fec_candidate_id=fec_candidate_id,
        )
        self._repo.save_rep(rep)
        return rep

    def resolve_donor(
        self,
        canonical_name: str,
        donor_type: str,
        fec_id: str,
        state: str | None = None,
    ) -> CanonicalDonor:
        """
        Upsert a canonical donor by FEC ID.

        If a donor with this FEC ID is already known, return them.
        Otherwise create a new canonical donor using the resolved canonical name.
        """
        existing = self._repo.find_donor_by_fec_id(fec_id)
        if existing is not None:
            return existing

        donor = CanonicalDonor(
            id=DonorId(str(ULID())),
            name=canonical_name,
            donor_type=_parse_donor_type(donor_type),
            industry=None,   # assigned by NLP in Sprint 7
            state=state,
            fec_ids=[fec_id],
        )
        self._repo.save_donor(donor)
        return donor

    def merge_donor_fec_id(self, donor: CanonicalDonor, fec_id: str) -> CanonicalDonor:
        """Add a new FEC ID to an existing canonical donor and persist."""
        if fec_id not in donor.fec_ids:
            donor.fec_ids.append(fec_id)
            self._repo.save_donor(donor)
        return donor


# ── Parsing helpers ───────────────────────────────────────────────────────────


def _parse_party(raw: str) -> Party:
    mapping = {"D": Party.DEMOCRAT, "R": Party.REPUBLICAN, "I": Party.INDEPENDENT}
    return mapping.get(raw.upper()[:1], Party.OTHER)


def _parse_chamber(raw: str) -> Chamber:
    return Chamber.SENATE if raw.lower().startswith("s") else Chamber.HOUSE


def _parse_donor_type(raw: str) -> DonorType:
    raw = raw.lower()
    if "individual" in raw:
        return DonorType.INDIVIDUAL
    if "pac" in raw:
        return DonorType.PAC
    if "corp" in raw:
        return DonorType.CORPORATION
    if "union" in raw:
        return DonorType.UNION
    return DonorType.OTHER
