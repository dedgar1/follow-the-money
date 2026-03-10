"""
Smoke test — hits the real FEC, Congress.gov, and Senate XML APIs.
Run with: uv run python infrastructure/scripts/smoke_test_apis.py
"""

from __future__ import annotations

import sys

from adapters.external.congress_client import CongressApiError, CongressGovClient
from adapters.external.fec_client import FECApiClient, FECApiError
from adapters.external.senate_xml_client import SenateXmlClient, SenateXmlError
from infrastructure.config import get_settings


def test_fec() -> bool:
    print("\n── FEC API ──────────────────────────────────────────────────────")
    try:
        with FECApiClient() as fec:
            contributions = []
            for record in fec.get_contributions(two_year_transaction_period=2024):
                contributions.append(record)
                if len(contributions) >= 3:
                    break

        if not contributions:
            print("  WARN: no contributions returned")
            return False

        print(f"  get_contributions(cycle=2024): {len(contributions)} records fetched")
        s = contributions[0]
        print(f"  Sample contributor: {s.get('contributor_name', 'N/A')!r}")
        print(f"  Sample amount:      ${s.get('contribution_receipt_amount', 0):,.2f}")
        print(f"  Sample date:        {s.get('contribution_receipt_date', 'N/A')}")
        print("  FEC API: OK")
        return True

    except FECApiError as exc:
        print(f"  FEC API ERROR: {exc}")
        return False
    except Exception as exc:
        print(f"  UNEXPECTED ERROR: {type(exc).__name__}: {exc}")
        return False


def test_congress_gov() -> bool:
    print("\n── Congress.gov API (House votes + Members) ─────────────────────")
    try:
        with CongressGovClient() as api:
            # Fetch first House vote summary for 119th Congress
            votes = []
            for v in api.get_house_votes(119, 1):
                votes.append(v)
                if len(votes) >= 1:
                    break

            if not votes:
                print("  WARN: no House votes returned")
                return False

            sample_vote = votes[0]
            roll_call = sample_vote.get("rollCallNumber", 0)
            print(f"  get_house_votes(119, 1): got vote #{roll_call}")
            print(f"  Result:   {sample_vote.get('result', 'N/A')!r}")
            print(f"  Date:     {sample_vote.get('startDate', 'N/A')[:10]}")
            print(f"  Bill:     {sample_vote.get('legislationType', '')}{sample_vote.get('legislationNumber', '')}")

            # Fetch member positions for this vote
            members = api.get_house_vote_members(119, 1, roll_call)
            print(f"  Member positions: {len(members)} members")
            if members:
                m = members[0]
                name = f"{m.get('firstName', '')} {m.get('lastName', '')}".strip()
                print(f"  Sample member: {name} ({m.get('voteParty', '')}-{m.get('voteState', '')}) → {m.get('voteCast', 'N/A')}")

            # Fetch one member
            members_list = []
            for mem in api.get_members(congress=119, chamber="House"):
                members_list.append(mem)
                if len(members_list) >= 1:
                    break
            if members_list:
                print(f"  get_members(House, 119): {members_list[0].get('name', 'N/A')!r}")

        print("  Congress.gov API: OK")
        return True

    except CongressApiError as exc:
        print(f"  Congress.gov ERROR: {exc}")
        return False
    except Exception as exc:
        print(f"  UNEXPECTED ERROR: {type(exc).__name__}: {exc}")
        return False


def test_senate_xml() -> bool:
    print("\n── Senate XML (roll call votes) ─────────────────────────────────")
    try:
        settings = get_settings()
        with SenateXmlClient() as senate:
            vote_list = senate.get_vote_list(settings.current_congress, settings.current_session)

            if not vote_list:
                print("  WARN: no Senate votes returned")
                return False

            print(f"  get_vote_list({settings.current_congress}, {settings.current_session}): "
                  f"{len(vote_list)} votes")
            s = vote_list[0]
            print(f"  First vote #{s['roll_call']}: {s['question']!r}")
            print(f"  Result: {s['result']}  ({s['yeas']} yeas / {s['nays']} nays)")
            print(f"  Date:   {s['date']}")

            # Fetch full detail of the first vote (includes per-senator positions)
            detail = senate.get_vote_detail(
                settings.current_congress, settings.current_session, s["roll_call"]
            )
            print(f"  Detail: {len(detail['members'])} senators, "
                  f"bill_id={detail['bill_id']!r}")
            if detail["members"]:
                m = detail["members"][0]
                print(f"  Sample senator: {m['member_full']} ({m['party']}-{m['state']}) → {m['vote_cast']}")

        print("  Senate XML: OK")
        return True

    except SenateXmlError as exc:
        print(f"  Senate XML ERROR: {exc}")
        return False
    except Exception as exc:
        print(f"  UNEXPECTED ERROR: {type(exc).__name__}: {exc}")
        return False


if __name__ == "__main__":
    fec_ok = test_fec()
    congress_ok = test_congress_gov()
    senate_ok = test_senate_xml()

    print("\n── Summary ──────────────────────────────────────────────────────")
    print(f"  FEC API:          {'PASS' if fec_ok else 'FAIL'}")
    print(f"  Congress.gov API: {'PASS' if congress_ok else 'FAIL'}")
    print(f"  Senate XML:       {'PASS' if senate_ok else 'FAIL'}")

    sys.exit(0 if (fec_ok and congress_ok and senate_ok) else 1)
