"""
Congress.gov API v3 client — House votes, members, and bills.

Official docs: https://api.congress.gov
Free API key:  https://api.congress.gov/sign-up/

Rate limit: 5,000 requests/hour.
Pagination:  offset + limit (default 20, max 250).

Senate roll call votes are NOT available in this API yet — use SenateXmlClient.
"""

from __future__ import annotations

from typing import Any, Iterator

import httpx

from infrastructure.config import get_settings


class CongressApiError(Exception):
    """Raised when the Congress.gov API returns an error or unexpected response."""


class CongressGovClient:
    BASE_URL = "https://api.congress.gov/v3"
    PAGE_SIZE = 250  # maximum allowed

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        key = api_key or settings.congress_api_key
        if not key:
            raise CongressApiError(
                "CONGRESS_API_KEY is required — get a free key at https://api.congress.gov/sign-up/"
            )
        self._api_key = key
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            timeout=30.0,
            headers={"User-Agent": "FollowTheMoney/1.0"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> CongressGovClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ── House Roll Call Votes (beta, 118th Congress onward) ───────────────────

    def get_house_votes(
        self,
        congress: int,
        session: int,
    ) -> Iterator[dict[str, Any]]:
        """
        Yield every House roll call vote summary for a congress/session.

        Each yielded dict is a vote-level summary (no per-member breakdown).
        Call get_house_vote_members() for the per-member positions.
        """
        yield from self._paginate(f"/house-vote/{congress}/{session}")

    def get_house_vote(
        self, congress: int, session: int, roll_call: int
    ) -> dict[str, Any]:
        """Fetch full detail for a single House roll call vote."""
        data = self._get(f"/house-vote/{congress}/{session}/{roll_call}")
        votes = data.get("houseRollCallVote") or data.get("houseVote")
        if not votes:
            raise CongressApiError(
                f"House vote not found: congress={congress} session={session} roll_call={roll_call}"
            )
        return votes if isinstance(votes, dict) else votes[0]

    def get_house_vote_members(
        self, congress: int, session: int, roll_call: int
    ) -> list[dict[str, Any]]:
        """
        Return the per-member vote positions for a specific House roll call.

        Each item has: bioguideID, firstName, lastName, voteCast, voteParty, voteState.
        """
        data = self._get(f"/house-vote/{congress}/{session}/{roll_call}/members")
        # Response: {"houseRollCallVoteMemberVotes": {"results": [...], ...}}
        wrapper = data.get("houseRollCallVoteMemberVotes", {})
        return wrapper.get("results", [])

    # ── Members ───────────────────────────────────────────────────────────────

    def get_members(
        self,
        congress: int | None = None,
        chamber: str | None = None,
        current_member: bool = True,
    ) -> Iterator[dict[str, Any]]:
        """
        Yield all member records matching the filters.

        Args:
            congress: Congress number (e.g. 119).
            chamber: "House" or "Senate".
            current_member: If True, only return currently serving members.
        """
        params: dict[str, Any] = {"currentMember": str(current_member).lower()}
        if congress:
            params["congress"] = congress
        if chamber:
            params["chamber"] = chamber
        yield from self._paginate("/member", extra_params=params)

    def get_member(self, bioguide_id: str) -> dict[str, Any]:
        """Fetch a single member by bioguide_id (e.g. 'A000370')."""
        data = self._get(f"/member/{bioguide_id}")
        member = data.get("member")
        if not member:
            raise CongressApiError(f"Member not found: {bioguide_id}")
        return member

    # ── Bills ─────────────────────────────────────────────────────────────────

    def get_bill(
        self, congress: int, bill_type: str, bill_number: int | str
    ) -> dict[str, Any]:
        """
        Fetch bill details.

        Args:
            congress: Congress number, e.g. 119.
            bill_type: Lowercase type: "hr", "s", "hjres", "sjres", etc.
            bill_number: Bill number, e.g. 1.
        """
        data = self._get(f"/bill/{congress}/{bill_type.lower()}/{bill_number}")
        bill = data.get("bill")
        if not bill:
            raise CongressApiError(
                f"Bill not found: {bill_type}{bill_number} (congress {congress})"
            )
        return bill

    def get_bills(
        self, congress: int, bill_type: str | None = None
    ) -> Iterator[dict[str, Any]]:
        """Yield all bills for a congress, optionally filtered by type."""
        path = f"/bill/{congress}"
        if bill_type:
            path += f"/{bill_type.lower()}"
        yield from self._paginate(path)

    # ── Pagination helper ─────────────────────────────────────────────────────

    def _paginate(
        self, path: str, extra_params: dict[str, Any] | None = None
    ) -> Iterator[dict[str, Any]]:
        """Transparently page through any list-level endpoint."""
        offset = 0
        while True:
            params: dict[str, Any] = {
                "api_key": self._api_key,
                "limit": self.PAGE_SIZE,
                "offset": offset,
                "format": "json",
            }
            if extra_params:
                params.update(extra_params)

            response = self._client.get(path, params=params)
            _raise_for_status(response)
            body = response.json()

            # The top-level key varies by endpoint — grab the first list value.
            items = _extract_list(body)
            for item in items:
                yield item

            pagination = body.get("pagination", {})
            total = pagination.get("count", len(items))
            offset += self.PAGE_SIZE
            if offset >= total or len(items) < self.PAGE_SIZE:
                break

    def _get(self, path: str) -> dict[str, Any]:
        """Fetch a single item endpoint."""
        params = {"api_key": self._api_key, "format": "json"}
        response = self._client.get(path, params=params)
        _raise_for_status(response)
        return response.json()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _extract_list(body: dict[str, Any]) -> list[dict[str, Any]]:
    """
    The Congress.gov API uses different top-level keys per endpoint
    (e.g. 'houseRollCallVotes', 'members', 'bills').
    Find the first list-typed value.
    """
    skip = {"pagination", "request"}
    for key, value in body.items():
        if key not in skip and isinstance(value, list):
            return value
    return []


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 429:
        raise CongressApiError("Congress.gov API rate limit exceeded (5000/hour)")
    if response.status_code in (401, 403):
        raise CongressApiError("Congress.gov API key invalid — check CONGRESS_API_KEY")
    if response.status_code == 404:
        raise CongressApiError(f"Congress.gov resource not found: {response.url}")
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise CongressApiError(
            f"Congress.gov API HTTP {response.status_code}: {response.text[:200]}"
        ) from exc
