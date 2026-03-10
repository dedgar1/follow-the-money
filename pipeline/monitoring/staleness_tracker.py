"""
Staleness tracker — records last successful pipeline run timestamp in Redis.

The frontend shows a staleness banner when data is >24h old.
Key stored: "pipeline:last_updated" → ISO 8601 UTC timestamp string.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from infrastructure.redis_client import get_redis_client

_REDIS_KEY = "pipeline:last_updated"
_STALE_AFTER_HOURS = 24


class StalenessTracker:
    """Redis-backed tracker for pipeline run timestamps."""

    def record_success(self) -> None:
        """Write the current UTC timestamp as the last successful run."""
        now = datetime.now(timezone.utc).isoformat()
        get_redis_client().set(_REDIS_KEY, now)

    def get_last_updated(self) -> datetime | None:
        """Return the timestamp of the last successful pipeline run, or None."""
        raw = get_redis_client().get(_REDIS_KEY)
        if raw is None:
            return None
        return datetime.fromisoformat(raw)

    def is_stale(self) -> bool:
        """Return True if no successful run has been recorded in the past 24 hours."""
        last = self.get_last_updated()
        if last is None:
            return True
        threshold = datetime.now(timezone.utc) - timedelta(hours=_STALE_AFTER_HOURS)
        return last < threshold


# Module-level convenience functions used by the API staleness endpoint.


def get_last_updated() -> datetime | None:
    """Return timestamp of last successful pipeline run."""
    return StalenessTracker().get_last_updated()


def is_stale() -> bool:
    """Return True if data is more than 24 hours old."""
    return StalenessTracker().is_stale()
