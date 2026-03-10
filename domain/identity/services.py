"""
Identity service — entity resolution and canonical lookup.

TODO Sprint 3: Implement EntityResolver using rapidfuzz for deduplication.
"""

from __future__ import annotations

from domain.identity.ports import IdentityRepository


class EntityResolver:
    """Resolves raw donor/rep names to canonical entities via fuzzy matching."""

    def __init__(self, repo: IdentityRepository) -> None:
        self._repo = repo

    # TODO Sprint 3: resolve_donor, resolve_rep, merge_duplicates
