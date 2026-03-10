"""
Senate roll call votes client — parses the Senate's official XML feeds.

The Congress.gov API does not yet provide Senate vote data, so we go
directly to the Senate's public XML files. No API key required.

Vote list:  https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_{congress}_{session}.xml
Vote detail: https://www.senate.gov/legislative/LIS/roll_call_votes/vote{congress}{session}/vote_{congress}_{session}_{padded_number}.xml

Each detail record contains the full per-senator vote breakdown.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Iterator

import httpx


class SenateXmlError(Exception):
    """Raised on HTTP or parse failures from the Senate XML feeds."""


class SenateXmlClient:
    VOTE_LIST_URL = (
        "https://www.senate.gov/legislative/LIS/roll_call_lists"
        "/vote_menu_{congress}_{session}.xml"
    )
    VOTE_DETAIL_URL = (
        "https://www.senate.gov/legislative/LIS/roll_call_votes"
        "/vote{congress}{session}/vote_{congress}_{session}_{roll_call:05d}.xml"
    )

    def __init__(self) -> None:
        self._client = httpx.Client(
            timeout=30.0,
            headers={"User-Agent": "FollowTheMoney/1.0"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> SenateXmlClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ── Vote list ─────────────────────────────────────────────────────────────

    def get_vote_list(self, congress: int, session: int) -> list[dict[str, Any]]:
        """
        Return a list of vote summary dicts for a congress/session.

        Each dict has: roll_call (int), date (str), issue (str),
        question (str), result (str), title (str), yeas (int), nays (int).
        """
        url = self.VOTE_LIST_URL.format(congress=congress, session=session)
        response = self._client.get(url)
        _raise_for_status(response, url)
        return _parse_vote_list(response.text)

    # ── Vote detail ───────────────────────────────────────────────────────────

    def get_vote_detail(
        self, congress: int, session: int, roll_call: int
    ) -> dict[str, Any]:
        """
        Fetch and parse a single Senate roll call vote.

        Returns a dict with top-level vote metadata and a 'members' list.
        Each member entry: member_full, last_name, first_name, party, state,
        lis_member_id, vote_cast.
        """
        url = self.VOTE_DETAIL_URL.format(
            congress=congress, session=session, roll_call=roll_call
        )
        response = self._client.get(url)
        _raise_for_status(response, url)
        return _parse_vote_detail(response.text)

    def get_all_vote_details(
        self, congress: int, session: int
    ) -> Iterator[dict[str, Any]]:
        """
        Yield full vote detail for every roll call in a congress/session.

        Fetches the vote list first, then fetches each vote individually.
        """
        for summary in self.get_vote_list(congress, session):
            roll_call = summary["roll_call"]
            try:
                detail = self.get_vote_detail(congress, session, roll_call)
                yield detail
            except SenateXmlError as exc:
                # Log and continue — a missing vote shouldn't halt the whole ingest
                import logging
                logging.getLogger(__name__).warning(
                    "senate_xml: skipping vote %d: %s", roll_call, exc
                )


# ── XML parsers ───────────────────────────────────────────────────────────────


def _parse_vote_list(xml_text: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SenateXmlError(f"Failed to parse Senate vote list XML: {exc}") from exc

    votes = []
    for vote_el in root.findall(".//vote"):
        tally_el = vote_el.find("vote_tally")
        votes.append({
            "roll_call": int(_text(vote_el, "vote_number", "0")),
            "date": _text(vote_el, "vote_date"),
            "issue": _text(vote_el, "issue"),
            "question": _text(vote_el, "question"),
            "result": _text(vote_el, "result"),
            "title": _text(vote_el, "title"),
            "yeas": int(_text(tally_el, "yeas", "0")) if tally_el is not None else 0,
            "nays": int(_text(tally_el, "nays", "0")) if tally_el is not None else 0,
        })
    return votes


def _parse_vote_detail(xml_text: str) -> dict[str, Any]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SenateXmlError(f"Failed to parse Senate vote detail XML: {exc}") from exc

    count_el = root.find("count")
    doc_el = root.find("document")

    members = []
    for m in root.findall(".//member"):
        members.append({
            "member_full": _text(m, "member_full"),
            "last_name": _text(m, "last_name"),
            "first_name": _text(m, "first_name"),
            "party": _text(m, "party"),
            "state": _text(m, "state"),
            "lis_member_id": _text(m, "lis_member_id"),
            "vote_cast": _text(m, "vote_cast"),
        })

    return {
        "congress": int(_text(root, "congress", "0")),
        "session": int(_text(root, "session", "0")),
        "roll_call": int(_text(root, "vote_number", "0")),
        "vote_date": _text(root, "vote_date"),
        "question": _text(root, "question"),
        "vote_title": _text(root, "vote_title"),
        "vote_result": _text(root, "vote_result"),
        "vote_question_text": _text(root, "vote_question_text"),
        "vote_document_text": _text(root, "vote_document_text"),
        "yeas": int(_text(count_el, "yeas", "0")) if count_el is not None else 0,
        "nays": int(_text(count_el, "nays", "0")) if count_el is not None else 0,
        "present": int(_text(count_el, "present", "0")) if count_el is not None else 0,
        "absent": int(_text(count_el, "absent", "0")) if count_el is not None else 0,
        "bill_id": _text(doc_el, "document_number") if doc_el is not None else "",
        "bill_title": _text(doc_el, "document_title") if doc_el is not None else "",
        "members": members,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────


def _text(el: ET.Element | None, tag: str, default: str = "") -> str:
    if el is None:
        return default
    child = el.find(tag)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _raise_for_status(response: httpx.Response, url: str) -> None:
    if response.status_code == 404:
        raise SenateXmlError(f"Senate XML not found: {url}")
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise SenateXmlError(
            f"Senate XML HTTP {response.status_code}: {url}"
        ) from exc
