"""
rapidfuzz-based entity resolver — deduplicates donor and representative names.

Problem: FEC filings contain the same donor under many spellings:
  "GOOGLE INC", "GOOGLE LLC", "GOOGLE, INC.", "Google Inc." → one CanonicalDonor

Approach:
  1. Normalise all names (uppercase, strip punctuation, collapse whitespace).
  2. For each incoming name, find the best match in the known-canonical index
     using token_sort_ratio (handles word-order variations).
  3. If score >= MATCH_THRESHOLD → same entity. Merge FEC IDs into existing canonical.
  4. If score < MATCH_THRESHOLD → new canonical entity.

Token sort ratio is preferred over simple ratio because donor names often
have legal suffixes in different positions: "SMITH JOHN PAC" vs "PAC SMITH JOHN".
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from rapidfuzz import process as rf_process
from rapidfuzz.fuzz import token_sort_ratio

# Score out of 100. 92 is tight enough to avoid false merges while catching
# common variations (LLC vs INC, punctuation, abbreviations).
MATCH_THRESHOLD = 92


@dataclass
class DonorCluster:
    """A group of raw donor name strings resolved to one canonical name."""

    canonical_name: str               # The normalised representative name for this cluster
    raw_names: list[str] = field(default_factory=list)   # Every raw string seen
    fec_ids: list[str] = field(default_factory=list)     # All FEC committee/transaction IDs


class DonorNameResolver:
    """
    Incrementally clusters raw FEC donor names into canonical groups.

    Usage:
        resolver = DonorNameResolver()
        for raw_name, fec_id in raw_records:
            resolver.add(raw_name, fec_id)
        clusters = resolver.clusters  # list[DonorCluster]
    """

    def __init__(self, threshold: int = MATCH_THRESHOLD) -> None:
        self._threshold = threshold
        self._clusters: list[DonorCluster] = []
        # Parallel list of normalised canonical names for rapidfuzz lookup
        self._index: list[str] = []

    def add(self, raw_name: str, fec_id: str = "") -> DonorCluster:
        """
        Add a raw donor name. Returns the cluster it was merged into (or the
        new cluster created for it).
        """
        normalised = normalise(raw_name)
        if not normalised:
            normalised = raw_name.strip() or "UNKNOWN"

        match = self._find_match(normalised)
        if match is not None:
            match.raw_names.append(raw_name)
            if fec_id and fec_id not in match.fec_ids:
                match.fec_ids.append(fec_id)
            return match

        # New cluster
        cluster = DonorCluster(
            canonical_name=normalised,
            raw_names=[raw_name],
            fec_ids=[fec_id] if fec_id else [],
        )
        self._clusters.append(cluster)
        self._index.append(normalised)
        return cluster

    def batch_add(self, records: list[tuple[str, str]]) -> None:
        """Add many (raw_name, fec_id) pairs at once."""
        for raw_name, fec_id in records:
            self.add(raw_name, fec_id)

    @property
    def clusters(self) -> list[DonorCluster]:
        return list(self._clusters)

    def _find_match(self, normalised: str) -> DonorCluster | None:
        if not self._index:
            return None
        result = rf_process.extractOne(
            normalised,
            self._index,
            scorer=token_sort_ratio,
            score_cutoff=self._threshold,
        )
        if result is None:
            return None
        _, _, idx = result
        return self._clusters[idx]


class RepNameResolver:
    """
    Matches raw representative name strings to their canonical bioguide_id.

    Simpler than donor resolution — reps have official IDs (bioguide_id) that
    serve as the ground truth. This resolver handles the case where a raw name
    from FEC data needs to be linked to an already-known canonical rep.

    Usage:
        resolver = RepNameResolver()
        resolver.index_known_reps([("A000370", "Alma Adams"), ...])
        bioguide_id = resolver.resolve("ADAMS, ALMA")
    """

    def __init__(self, threshold: int = MATCH_THRESHOLD) -> None:
        self._threshold = threshold
        self._bioguide_ids: list[str] = []
        self._index: list[str] = []   # normalised canonical names

    def index_known_reps(self, reps: list[tuple[str, str]]) -> None:
        """
        Load known (bioguide_id, full_name) pairs into the search index.
        Call this once before resolving.
        """
        for bioguide_id, full_name in reps:
            self._bioguide_ids.append(bioguide_id)
            self._index.append(normalise(full_name))

    def resolve(self, raw_name: str) -> str | None:
        """
        Return the bioguide_id for the best name match, or None if below threshold.
        """
        if not self._index:
            return None
        normalised = normalise(raw_name)
        result = rf_process.extractOne(
            normalised,
            self._index,
            scorer=token_sort_ratio,
            score_cutoff=self._threshold,
        )
        if result is None:
            return None
        _, _, idx = result
        return self._bioguide_ids[idx]


# ── Text normalisation ────────────────────────────────────────────────────────

# Legal suffixes to strip before comparison — they cause false non-matches
# between "GOOGLE INC" and "GOOGLE LLC".
_LEGAL_SUFFIXES = re.compile(
    r"\b(INC|LLC|LLP|LP|LTD|CORP|CORPORATION|CO|COMPANY|INCORPORATED|LIMITED|"
    r"PAC|COMMITTEE|FUND|ASSOCIATION|ASSOC|ASSN|TRUST|GROUP|FOUNDATION)\b",
    re.IGNORECASE,
)
_PUNCT = re.compile(r"[^\w\s]")
_WHITESPACE = re.compile(r"\s+")


def normalise(name: str) -> str:
    """
    Normalise a donor/rep name for fuzzy comparison.

    Steps:
      1. Unicode NFC normalisation
      2. Uppercase
      3. Strip legal suffixes (INC, LLC, etc.)
      4. Remove punctuation
      5. Collapse whitespace
    """
    # NFC normalise handles accented characters consistently
    name = unicodedata.normalize("NFC", name).upper()
    name = _LEGAL_SUFFIXES.sub("", name)
    name = _PUNCT.sub(" ", name)
    name = _WHITESPACE.sub(" ", name).strip()
    return name
