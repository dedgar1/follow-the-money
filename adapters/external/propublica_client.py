"""
ProPublica Congress API client — fetches roll call votes, bills, sponsorships.

TODO Sprint 2: Implement ProPublica API integration.
Docs: https://projects.propublica.org/api-docs/congress-api/
"""

from __future__ import annotations


class ProPublicaClient:
    BASE_URL = "https://api.propublica.org/congress/v1"

    # TODO Sprint 2: get_recent_votes, get_bill, get_member_votes
