"""
FEC API client — fetches individual contributions and PAC donations.

Docs: https://api.open.fec.gov/developers/
Rate limits: 1000 req/hour (API key required), 20 req/hour (no key).
Pagination: uses `last_indexes` cursor pattern for stable pagination.
"""

from __future__ import annotations

from typing import Any, Iterator

import httpx

from infrastructure.config import get_settings


class FECApiError(Exception):
    """Raised when the FEC API returns an error or unexpected response."""


class FECApiClient:
    BASE_URL = "https://api.open.fec.gov/v1"
    DEFAULT_PER_PAGE = 100

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.fec_api_key or "DEMO_KEY"
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            timeout=30.0,
            headers={"User-Agent": "FollowTheMoney/1.0"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> FECApiClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ── Contributions ─────────────────────────────────────────────────────────

    def get_contributions(
        self,
        *,
        committee_id: str | None = None,
        two_year_transaction_period: int | None = None,
        min_date: str | None = None,
        max_date: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """
        Yield all Schedule A (individual contributions) records matching the filters.

        Transparently handles FEC cursor-based pagination — callers receive a flat
        iterator of raw API result dicts, one per filing record.
        """
        params: dict[str, Any] = {
            "api_key": self._api_key,
            "per_page": self.DEFAULT_PER_PAGE,
            "sort": "contribution_receipt_date",
        }
        if committee_id:
            params["committee_id"] = committee_id
        if two_year_transaction_period:
            params["two_year_transaction_period"] = two_year_transaction_period
        if min_date:
            params["min_date"] = min_date
        if max_date:
            params["max_date"] = max_date

        last_indexes: dict[str, Any] | None = None

        while True:
            if last_indexes:
                params.update(last_indexes)

            response = self._client.get("/schedules/schedule_a/", params=params)
            _raise_for_status(response)
            body = response.json()

            results: list[dict[str, Any]] = body.get("results", [])
            for record in results:
                yield record

            pagination = body.get("pagination", {})
            last_indexes = pagination.get("last_indexes")
            if not last_indexes or len(results) < self.DEFAULT_PER_PAGE:
                break

    # ── Candidate ─────────────────────────────────────────────────────────────

    def get_candidate(self, candidate_id: str) -> dict[str, Any]:
        """Fetch a single candidate record by FEC candidate_id."""
        params = {"api_key": self._api_key}
        response = self._client.get(f"/candidate/{candidate_id}/", params=params)
        _raise_for_status(response)
        results = response.json().get("results", [])
        if not results:
            raise FECApiError(f"Candidate not found: {candidate_id}")
        return results[0]

    def get_candidates(
        self,
        *,
        state: str | None = None,
        chamber: str | None = None,
        cycle: int | None = None,
        office: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """
        Yield all candidate records matching the filters.

        Args:
            state: Two-letter state code, e.g. "CA".
            chamber: "H" (House) or "S" (Senate).
            cycle: Election cycle year, e.g. 2024.
            office: "H", "S", or "P" (President).
        """
        params: dict[str, Any] = {
            "api_key": self._api_key,
            "per_page": self.DEFAULT_PER_PAGE,
            "is_active_candidate": True,
        }
        if state:
            params["state"] = state
        if chamber or office:
            params["office"] = chamber or office
        if cycle:
            params["cycle"] = cycle

        page = 1
        while True:
            params["page"] = page
            response = self._client.get("/candidates/", params=params)
            _raise_for_status(response)
            body = response.json()
            results = body.get("results", [])
            for record in results:
                yield record
            pagination = body.get("pagination", {})
            if page >= pagination.get("pages", 1):
                break
            page += 1

    # ── Committee ─────────────────────────────────────────────────────────────

    def get_committee(self, committee_id: str) -> dict[str, Any]:
        """Fetch a single committee record by FEC committee_id."""
        params = {"api_key": self._api_key}
        response = self._client.get(f"/committee/{committee_id}/", params=params)
        _raise_for_status(response)
        results = response.json().get("results", [])
        if not results:
            raise FECApiError(f"Committee not found: {committee_id}")
        return results[0]

    def get_committees_for_candidate(self, candidate_id: str) -> list[dict[str, Any]]:
        """Fetch all committees linked to a candidate."""
        params = {"api_key": self._api_key, "per_page": self.DEFAULT_PER_PAGE}
        response = self._client.get(
            f"/candidate/{candidate_id}/committees/", params=params
        )
        _raise_for_status(response)
        return response.json().get("results", [])


# ── Helpers ───────────────────────────────────────────────────────────────────


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 429:
        raise FECApiError("FEC API rate limit exceeded — retry after cooling off")
    if response.status_code == 403:
        raise FECApiError("FEC API key invalid or missing")
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise FECApiError(
            f"FEC API HTTP {response.status_code}: {response.text[:200]}"
        ) from exc
