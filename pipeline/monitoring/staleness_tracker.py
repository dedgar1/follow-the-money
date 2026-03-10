"""
Staleness tracker — records last successful pipeline run timestamp.

TODO Sprint 2: Persist staleness state to Redis and expose to API.
The frontend shows a staleness banner when data is >24h old.
"""

from __future__ import annotations

from datetime import datetime


class StalenessTracker:
    # TODO Sprint 2: record_success, get_last_updated, is_stale
    pass


def get_last_updated() -> datetime | None:
    """TODO Sprint 2: Return timestamp of last successful pipeline run."""
    return None
