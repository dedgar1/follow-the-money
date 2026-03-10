"""
ProPublica Congress API — DISCONTINUED July 10, 2024.

Use CongressGovClient (congress_client.py) for House votes, members, and bills.
Use SenateXmlClient (senate_xml_client.py) for Senate roll call votes.

Reference: https://www.propublica.org/datastore/api/propublica-congress-api
"""

from __future__ import annotations


class ProPublicaApiError(Exception):
    pass


class ProPublicaClient:
    def __init__(self, *args, **kwargs) -> None:
        raise ProPublicaApiError(
            "ProPublica Congress API was discontinued on July 10, 2024. "
            "Use CongressGovClient for House votes/members/bills, "
            "and SenateXmlClient for Senate votes."
        )
