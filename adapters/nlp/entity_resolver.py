"""
rapidfuzz-based entity resolver — deduplicates donor names.

Examples:
  "GOOGLE INC" + "GOOGLE LLC" + "Google, Inc." → one CanonicalDonor

TODO Sprint 3: Implement using rapidfuzz.
"""

from __future__ import annotations


class EntityResolver:
    # TODO Sprint 3: resolve_donor_name, batch_resolve, merge_fec_ids
    pass
