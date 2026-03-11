"""
Seed development database with realistic sample data.

Creates:
  - 25 canonical representatives (House + Senate, D/R/I, various states)
  - 12 canonical donors (PACs, corporations, unions across key industries)
  - ~60 funding relationships with realistic donation amounts
  - 15 bills (119th Congress, 2025) + 7 historical bills (118th Congress, 2022-2024)
  - ~150 vote records (2025) + ~60 historical votes (2022-2024) for before/after windows
  - AlignmentScores for 3 (rep, industry) pairs with clearly significant shifts
  - Neo4j graph nodes + FUNDED edges (skipped gracefully if Neo4j is unavailable)

Usage:
  python infrastructure/scripts/seed_dev_data.py
  python infrastructure/scripts/seed_dev_data.py --reset   # drop + recreate all rows
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

from sqlalchemy import text

# Ensure project root is on sys.path when run directly
sys.path.insert(0, __file__.rsplit("/infrastructure", 1)[0])

from adapters.postgres.orm_models import (
    AlignmentScoreRow,
    Base,
    BillRow,
    CanonicalDonorRow,
    CanonicalRelationshipRow,
    CanonicalRepRow,
    RawVoteRow,
)
from infrastructure.database import engine, get_session

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# ── Seed data ──────────────────────────────────────────────────────────────────

REPS = [
    # House Democrats
    dict(id="REP001", full_name="Maria Elena Vasquez",   party="D", chamber="house",  state="CA", district="CA-18", bioguide_id="V000001", fec_candidate_id="H2CA18001"),
    dict(id="REP002", full_name="James T. Whitfield",    party="D", chamber="house",  state="NY", district="NY-12", bioguide_id="W000002", fec_candidate_id="H2NY12001"),
    dict(id="REP003", full_name="Priya Chandrasekaran",  party="D", chamber="house",  state="TX", district="TX-07", bioguide_id="C000003", fec_candidate_id="H2TX07001"),
    dict(id="REP004", full_name="Robert L. Nguyen",      party="D", chamber="house",  state="WA", district="WA-09", bioguide_id="N000004", fec_candidate_id="H2WA09001"),
    dict(id="REP005", full_name="Sandra Kowalski",       party="D", chamber="house",  state="IL", district="IL-05", bioguide_id="K000005", fec_candidate_id="H2IL05001"),
    dict(id="REP006", full_name="DeShawn A. Brooks",     party="D", chamber="house",  state="GA", district="GA-05", bioguide_id="B000006", fec_candidate_id="H2GA05001"),
    dict(id="REP007", full_name="Yuki Tanaka-Morrison",  party="D", chamber="house",  state="OR", district="OR-03", bioguide_id="T000007", fec_candidate_id="H2OR03001"),
    dict(id="REP008", full_name="Claudette Moreau",      party="D", chamber="house",  state="MA", district="MA-07", bioguide_id="M000008", fec_candidate_id="H2MA07001"),
    dict(id="REP009", full_name="Kwame Osei-Bonsu",      party="D", chamber="house",  state="MD", district="MD-04", bioguide_id="O000009", fec_candidate_id="H2MD04001"),
    dict(id="REP010", full_name="Ingrid Halvorsen",      party="D", chamber="house",  state="MN", district="MN-05", bioguide_id="H000010", fec_candidate_id="H2MN05001"),
    # House Republicans
    dict(id="REP011", full_name="Bradley J. Harmon",     party="R", chamber="house",  state="TX", district="TX-02", bioguide_id="H000011", fec_candidate_id="H2TX02001"),
    dict(id="REP012", full_name="Patricia Weston",       party="R", chamber="house",  state="FL", district="FL-01", bioguide_id="W000012", fec_candidate_id="H2FL01001"),
    dict(id="REP013", full_name="Carl R. Stanton",       party="R", chamber="house",  state="OH", district="OH-07", bioguide_id="S000013", fec_candidate_id="H2OH07001"),
    dict(id="REP014", full_name="Meredith A. Pruitt",    party="R", chamber="house",  state="GA", district="GA-07", bioguide_id="P000014", fec_candidate_id="H2GA07001"),
    dict(id="REP015", full_name="Douglas McAllister",    party="R", chamber="house",  state="NC", district="NC-09", bioguide_id="M000015", fec_candidate_id="H2NC09001"),
    dict(id="REP016", full_name="Jennifer Holcomb",      party="R", chamber="house",  state="AZ", district="AZ-06", bioguide_id="H000016", fec_candidate_id="H2AZ06001"),
    dict(id="REP017", full_name="Travis E. Beaumont",    party="R", chamber="house",  state="LA", district="LA-04", bioguide_id="B000017", fec_candidate_id="H2LA04001"),
    dict(id="REP018", full_name="Kimberly Frazier",      party="R", chamber="house",  state="KY", district="KY-05", bioguide_id="F000018", fec_candidate_id="H2KY05001"),
    # Senate Democrats
    dict(id="REP019", full_name="Eleanor H. Davenport",  party="D", chamber="senate", state="CA", district=None,    bioguide_id="D000019", fec_candidate_id="S2CA00001"),
    dict(id="REP020", full_name="Marcus T. Jefferson",   party="D", chamber="senate", state="NY", district=None,    bioguide_id="J000020", fec_candidate_id="S2NY00001"),
    dict(id="REP021", full_name="Nadia Al-Rashid",       party="D", chamber="senate", state="MI", district=None,    bioguide_id="A000021", fec_candidate_id="S2MI00001"),
    dict(id="REP022", full_name="Helena Cruz-Reyes",     party="D", chamber="senate", state="CO", district=None,    bioguide_id="C000022", fec_candidate_id="S2CO00001"),
    # Senate Republicans
    dict(id="REP023", full_name="Randall T. Boone",      party="R", chamber="senate", state="TX", district=None,    bioguide_id="B000023", fec_candidate_id="S2TX00001"),
    dict(id="REP024", full_name="Constance M. Shields",  party="R", chamber="senate", state="FL", district=None,    bioguide_id="S000024", fec_candidate_id="S2FL00001"),
    # Senate Independent
    dict(id="REP025", full_name="Bernard A. Whitmore",   party="I", chamber="senate", state="VT", district=None,    bioguide_id="W000025", fec_candidate_id=None),
]

DONORS = [
    dict(id="DONOR001", name="Energy First PAC",             donor_type="pac",         industry="energy",        state="TX", fec_ids='["C00100001"]'),
    dict(id="DONOR002", name="Financial Services Roundtable", donor_type="pac",        industry="finance",       state="NY", fec_ids='["C00100002"]'),
    dict(id="DONOR003", name="TechForward PAC",              donor_type="pac",         industry="technology",    state="CA", fec_ids='["C00100003"]'),
    dict(id="DONOR004", name="HealthAmerica Alliance",       donor_type="pac",         industry="health",        state="DC", fec_ids='["C00100004"]'),
    dict(id="DONOR005", name="United Auto Workers PAC",      donor_type="union",       industry="labor",         state="MI", fec_ids='["C00100005"]'),
    dict(id="DONOR006", name="Meridian Petroleum Corp",      donor_type="corporation", industry="energy",        state="TX", fec_ids='["C00100006"]'),
    dict(id="DONOR007", name="Apex Capital Management",      donor_type="corporation", industry="finance",       state="NY", fec_ids='["C00100007"]'),
    dict(id="DONOR008", name="AgriGrowth PAC",               donor_type="pac",         industry="agriculture",   state="IA", fec_ids='["C00100008"]'),
    dict(id="DONOR009", name="National Defense Contractors", donor_type="pac",         industry="defense",       state="VA", fec_ids='["C00100009"]'),
    dict(id="DONOR010", name="Real Estate Owners Council",   donor_type="pac",         industry="real_estate",   state="FL", fec_ids='["C00100010"]'),
    dict(id="DONOR011", name="TelecomFirst PAC",             donor_type="pac",         industry="telecom",       state="DC", fec_ids='["C00100011"]'),
    dict(id="DONOR012", name="Teachers & Education PAC",     donor_type="union",       industry="education",     state="IL", fec_ids='["C00100012"]'),
]

# (donor_id, rep_id, total_cents, cycles, first_date, latest_date)
# Amounts reflect realistic FEC ranges: $5K–$500K
RELATIONSHIPS = [
    # Energy First PAC — funds energy-friendly reps in TX, LA, OH
    ("DONOR001", "REP011", 50_000_00, [2022, 2024], "2022-03-15", "2024-09-12"),
    ("DONOR001", "REP017", 42_500_00, [2022, 2024], "2022-05-01", "2024-08-30"),
    ("DONOR001", "REP013", 38_000_00, [2022, 2024], "2022-04-10", "2024-07-20"),
    ("DONOR001", "REP023", 75_000_00, [2020, 2022, 2024], "2020-01-10", "2024-10-01"),
    ("DONOR001", "REP024", 60_000_00, [2022, 2024], "2022-02-14", "2024-09-28"),
    ("DONOR001", "REP003", 15_000_00, [2024], "2024-03-01", "2024-03-01"),  # cross-party

    # Financial Services Roundtable — broad bipartisan giving
    ("DONOR002", "REP001", 30_000_00, [2022, 2024], "2022-06-01", "2024-08-15"),
    ("DONOR002", "REP002", 45_000_00, [2022, 2024], "2022-07-20", "2024-09-10"),
    ("DONOR002", "REP011", 55_000_00, [2022, 2024], "2022-03-01", "2024-10-02"),
    ("DONOR002", "REP019", 120_000_00, [2020, 2022, 2024], "2020-02-01", "2024-09-01"),
    ("DONOR002", "REP020", 95_000_00, [2022, 2024], "2022-01-15", "2024-10-05"),
    ("DONOR002", "REP023", 80_000_00, [2022, 2024], "2022-04-01", "2024-08-20"),

    # TechForward PAC — mostly D, coastal
    ("DONOR003", "REP001", 85_000_00, [2022, 2024], "2022-02-01", "2024-10-15"),
    ("DONOR003", "REP004", 72_000_00, [2022, 2024], "2022-03-15", "2024-09-30"),
    ("DONOR003", "REP007", 48_000_00, [2022, 2024], "2022-05-01", "2024-08-01"),
    ("DONOR003", "REP019", 150_000_00, [2020, 2022, 2024], "2020-01-05", "2024-10-20"),
    ("DONOR003", "REP016", 20_000_00, [2024], "2024-04-01", "2024-04-01"),  # cross-party

    # HealthAmerica Alliance — health committee members
    ("DONOR004", "REP005", 40_000_00, [2022, 2024], "2022-04-01", "2024-07-15"),
    ("DONOR004", "REP008", 35_000_00, [2022, 2024], "2022-06-01", "2024-08-01"),
    ("DONOR004", "REP012", 45_000_00, [2022, 2024], "2022-03-01", "2024-09-01"),
    ("DONOR004", "REP021", 90_000_00, [2022, 2024], "2022-01-20", "2024-10-01"),
    ("DONOR004", "REP024", 55_000_00, [2022, 2024], "2022-02-15", "2024-09-15"),

    # UAW PAC — labor-aligned, mostly D industrial states
    ("DONOR005", "REP005", 25_000_00, [2022, 2024], "2022-08-01", "2024-09-01"),
    ("DONOR005", "REP009", 30_000_00, [2022, 2024], "2022-06-15", "2024-08-15"),
    ("DONOR005", "REP010", 28_000_00, [2022, 2024], "2022-07-01", "2024-09-20"),
    ("DONOR005", "REP021", 60_000_00, [2020, 2022, 2024], "2020-03-01", "2024-10-10"),
    ("DONOR005", "REP025", 20_000_00, [2022, 2024], "2022-05-01", "2024-08-01"),

    # Meridian Petroleum — heavy TX + energy committee
    ("DONOR006", "REP011", 95_000_00, [2020, 2022, 2024], "2020-01-15", "2024-10-20"),
    ("DONOR006", "REP017", 80_000_00, [2022, 2024], "2022-02-01", "2024-09-05"),
    ("DONOR006", "REP023", 200_000_00, [2020, 2022, 2024], "2020-01-01", "2024-10-25"),
    ("DONOR006", "REP013", 65_000_00, [2022, 2024], "2022-03-10", "2024-08-10"),

    # Apex Capital — finance-aligned, Senate heavy
    ("DONOR007", "REP019", 180_000_00, [2020, 2022, 2024], "2020-01-08", "2024-10-30"),
    ("DONOR007", "REP020", 160_000_00, [2020, 2022, 2024], "2020-02-10", "2024-10-28"),
    ("DONOR007", "REP023", 140_000_00, [2020, 2022, 2024], "2020-01-20", "2024-10-15"),
    ("DONOR007", "REP024", 130_000_00, [2020, 2022, 2024], "2020-02-20", "2024-10-12"),
    ("DONOR007", "REP002", 50_000_00, [2022, 2024], "2022-05-01", "2024-09-01"),

    # AgriGrowth PAC — rural R + farm states
    ("DONOR008", "REP015", 35_000_00, [2022, 2024], "2022-04-01", "2024-08-01"),
    ("DONOR008", "REP018", 30_000_00, [2022, 2024], "2022-05-01", "2024-07-01"),
    ("DONOR008", "REP023", 45_000_00, [2022, 2024], "2022-03-01", "2024-09-01"),
    ("DONOR008", "REP003", 12_000_00, [2024], "2024-02-01", "2024-02-01"),

    # Defense Contractors — armed services committee members
    ("DONOR009", "REP011", 40_000_00, [2022, 2024], "2022-04-01", "2024-09-01"),
    ("DONOR009", "REP014", 55_000_00, [2022, 2024], "2022-03-15", "2024-08-15"),
    ("DONOR009", "REP023", 90_000_00, [2020, 2022, 2024], "2020-02-01", "2024-10-01"),
    ("DONOR009", "REP024", 75_000_00, [2022, 2024], "2022-02-01", "2024-09-20"),

    # Real Estate — broad, FL + GA heavy
    ("DONOR010", "REP012", 50_000_00, [2022, 2024], "2022-03-01", "2024-09-01"),
    ("DONOR010", "REP014", 42_000_00, [2022, 2024], "2022-04-01", "2024-08-01"),
    ("DONOR010", "REP024", 85_000_00, [2020, 2022, 2024], "2020-01-15", "2024-10-01"),
    ("DONOR010", "REP001", 22_000_00, [2024], "2024-01-15", "2024-01-15"),

    # TelecomFirst — bipartisan, Senate-heavy
    ("DONOR011", "REP019", 70_000_00, [2022, 2024], "2022-01-10", "2024-10-01"),
    ("DONOR011", "REP020", 65_000_00, [2022, 2024], "2022-02-01", "2024-09-15"),
    ("DONOR011", "REP023", 80_000_00, [2022, 2024], "2022-01-20", "2024-10-10"),
    ("DONOR011", "REP016", 30_000_00, [2022, 2024], "2022-05-01", "2024-08-01"),
    ("DONOR011", "REP004", 25_000_00, [2024], "2024-03-01", "2024-03-01"),

    # Teachers & Education PAC — D-leaning, education committee
    ("DONOR012", "REP005", 28_000_00, [2022, 2024], "2022-06-01", "2024-09-01"),
    ("DONOR012", "REP008", 22_000_00, [2022, 2024], "2022-07-01", "2024-08-01"),
    ("DONOR012", "REP010", 18_000_00, [2022, 2024], "2022-08-01", "2024-07-01"),
    ("DONOR012", "REP021", 45_000_00, [2022, 2024], "2022-02-01", "2024-10-01"),
    ("DONOR012", "REP025", 15_000_00, [2022, 2024], "2022-05-01", "2024-08-01"),
]


# ── Bills (Sprint 7) ──────────────────────────────────────────────────────────
# 15 representative bills across the major industry categories.

BILLS = [
    dict(id="BILL001", title="American Clean Energy Act", industries='["energy_natural_resources"]',
         nlp_confidence=0.85, congress=119, congress_gov_id="hr1001"),
    dict(id="BILL002", title="Wall Street Reform and Consumer Protection Enhancement Act",
         industries='["finance_insurance_real_estate"]', nlp_confidence=0.88,
         congress=119, congress_gov_id="hr1002"),
    dict(id="BILL003", title="Affordable Health Care Improvement Act",
         industries='["health"]', nlp_confidence=0.90, congress=119, congress_gov_id="hr1003"),
    dict(id="BILL004", title="National Defense Authorization Act for Fiscal Year 2025",
         industries='["defense"]', nlp_confidence=0.92, congress=119, congress_gov_id="hr1004"),
    dict(id="BILL005", title="Farm Bill Agricultural Support and Rural Development Act",
         industries='["agriculture"]', nlp_confidence=0.87, congress=119, congress_gov_id="s1001"),
    dict(id="BILL006", title="Broadband Access and Net Neutrality Restoration Act",
         industries='["communications_electronics"]', nlp_confidence=0.83,
         congress=119, congress_gov_id="hr1006"),
    dict(id="BILL007", title="Highway Infrastructure and Transportation Investment Act",
         industries='["transportation"]', nlp_confidence=0.86, congress=119, congress_gov_id="hr1007"),
    dict(id="BILL008", title="Minimum Wage and Worker Protection Act",
         industries='["labor"]', nlp_confidence=0.91, congress=119, congress_gov_id="hr1008"),
    dict(id="BILL009", title="Prescription Drug Pricing Transparency Act",
         industries='["health"]', nlp_confidence=0.89, congress=119, congress_gov_id="s1002"),
    dict(id="BILL010", title="Pipeline Safety and Oil Spill Prevention Act",
         industries='["energy_natural_resources"]', nlp_confidence=0.84,
         congress=119, congress_gov_id="hr1010"),
    dict(id="BILL011", title="Mortgage Relief and Housing Finance Reform Act",
         industries='["finance_insurance_real_estate"]', nlp_confidence=0.82,
         congress=119, congress_gov_id="hr1011"),
    dict(id="BILL012", title="Criminal Justice Reform and Sentencing Guidelines Act",
         industries='["lawyers_lobbyists"]', nlp_confidence=0.79,
         congress=119, congress_gov_id="s1003"),
    dict(id="BILL013", title="Military Veterans Benefits Expansion Act",
         industries='["defense"]', nlp_confidence=0.88, congress=119, congress_gov_id="hr1013"),
    dict(id="BILL014", title="Medicare Advantage Modernization Act",
         industries='["health"]', nlp_confidence=0.91, congress=119, congress_gov_id="s1004"),
    dict(id="BILL015", title="Cybersecurity and Data Privacy Protection Act",
         industries='["communications_electronics"]', nlp_confidence=0.85,
         congress=119, congress_gov_id="hr1015"),
]

# ── Historical bills (118th Congress, 2022-2024) ──────────────────────────────
# Used to build "before" votes for the correlation demo.  Three target
# (rep, industry) pairs each get 6-8 votes before the major donation event.
#
#   REP011 (Bradley Harmon, R-TX) + energy_natural_resources
#     Donor event: DONOR006 → REP011, latest_donation = 2024-10-20
#   REP023 (Randall Boone, R-TX senator) + finance_insurance_real_estate
#     Donor event: DONOR007 → REP023, latest_donation = 2024-10-15
#   REP019 (Eleanor Davenport, D-CA senator) + communications_electronics
#     Donor event: DONOR003 → REP019, latest_donation = 2024-10-20

HISTORICAL_BILLS = [
    dict(id="BILL_H01", title="Fossil Fuel Infrastructure Expansion Act",
         industries='["energy_natural_resources"]', nlp_confidence=0.87,
         congress=118, congress_gov_id="hr3001"),
    dict(id="BILL_H02", title="Offshore Oil and Gas Drilling Authorization Act",
         industries='["energy_natural_resources"]', nlp_confidence=0.85,
         congress=118, congress_gov_id="hr3002"),
    dict(id="BILL_H03", title="Natural Gas Pipeline Deregulation Act",
         industries='["energy_natural_resources"]', nlp_confidence=0.83,
         congress=118, congress_gov_id="hr3003"),
    dict(id="BILL_H04", title="Banking Deregulation and Financial Innovation Act",
         industries='["finance_insurance_real_estate"]', nlp_confidence=0.88,
         congress=118, congress_gov_id="hr3004"),
    dict(id="BILL_H05", title="Securities Market Reform and Modernization Act",
         industries='["finance_insurance_real_estate"]', nlp_confidence=0.86,
         congress=118, congress_gov_id="s3001"),
    dict(id="BILL_H06", title="Internet Privacy and Technology Industry Regulation Act",
         industries='["communications_electronics"]', nlp_confidence=0.84,
         congress=118, congress_gov_id="hr3006"),
    dict(id="BILL_H07", title="Broadband Infrastructure and Net Neutrality Act",
         industries='["communications_electronics"]', nlp_confidence=0.82,
         congress=118, congress_gov_id="s3002"),
]


# ── Vote seed data (raw_votes) ─────────────────────────────────────────────────
# Format: (source_id, member_bioguide_id, member_name, bill_id, position, voted_at, chamber)
# Unique constraint: (source_id, member_bioguide_id)

def _build_votes() -> list[dict]:
    """Generate a realistic set of ~90 vote records for 12 House reps."""
    from ulid import ULID

    # (roll_call, bill_congress_gov_id, date, chamber)
    house_votes = [
        (1,  "hr1001", "2025-01-20", "House"),
        (2,  "hr1002", "2025-01-22", "House"),
        (3,  "hr1003", "2025-01-28", "House"),
        (4,  "hr1004", "2025-02-05", "House"),
        (5,  "hr1006", "2025-02-12", "House"),
        (6,  "hr1007", "2025-02-18", "House"),
        (7,  "hr1008", "2025-02-26", "House"),
        (8,  "hr1010", "2025-03-04", "House"),
        (9,  "hr1011", "2025-03-10", "House"),
        (10, "hr1013", "2025-03-18", "House"),
        (11, "hr1015", "2025-03-24", "House"),
    ]
    senate_votes = [
        (101, "s1001", "2025-01-23", "Senate"),
        (102, "s1002", "2025-02-06", "Senate"),
        (103, "s1003", "2025-02-27", "Senate"),
        (104, "s1004", "2025-03-13", "Senate"),
    ]

    # (bioguide_id, member_name, party)
    house_members = [
        ("V000001", "Maria Elena Vasquez",  "D"),
        ("W000002", "James T. Whitfield",   "D"),
        ("C000003", "Priya Chandrasekaran", "D"),
        ("N000004", "Robert L. Nguyen",     "D"),
        ("K000005", "Sandra Kowalski",      "D"),
        ("H000011", "Bradley J. Harmon",    "R"),
        ("W000012", "Patricia Weston",      "R"),
        ("S000013", "Carl R. Stanton",      "R"),
        ("P000014", "Meredith A. Pruitt",   "R"),
        ("M000015", "Douglas McAllister",   "R"),
    ]
    senate_members = [
        ("D000019", "Eleanor H. Davenport", "D"),
        ("J000020", "Marcus T. Jefferson",  "D"),
        ("B000023", "Randall T. Boone",     "R"),
        ("S000024", "Constance M. Shields", "R"),
    ]

    # Simulate realistic voting patterns:
    #   D reps: YES on clean energy, labor, health; NO on defense expansion
    #   R reps: YES on defense, energy (oil); NO on min wage, broadband
    def _position(party: str, bill_id: str) -> str:
        d_yes = {"hr1001", "hr1003", "hr1006", "hr1007", "hr1008", "hr1015", "s1002", "s1004"}
        r_yes = {"hr1004", "hr1010", "hr1013", "hr1002", "hr1011"}
        if party == "D":
            return "Yea" if bill_id in d_yes else "Nay"
        else:
            return "Yea" if bill_id in r_yes else "Nay"

    rows = []
    for roll_call, bill_id, voted_at, chamber in house_votes:
        source_id = f"house/119/1/{roll_call}"
        # Look up the bill title from BILLS list
        bill_title = next((b["title"] for b in BILLS if b["congress_gov_id"] == bill_id), bill_id)
        for bioguide_id, member_name, party in house_members:
            rows.append(dict(
                id=str(ULID()),
                source="congress_api",
                source_id=source_id,
                congress=119,
                session=1,
                chamber=chamber,
                roll_call=roll_call,
                bill_id=bill_id,
                bill_title=bill_title,
                member_bioguide_id=bioguide_id,
                member_name=member_name,
                position=_position(party, bill_id),
                voted_at=voted_at,
                payload={},
                is_processed=False,
            ))

    for roll_call, bill_id, voted_at, chamber in senate_votes:
        source_id = f"senate/119/1/{roll_call}"
        bill_title = next((b["title"] for b in BILLS if b["congress_gov_id"] == bill_id), bill_id)
        for bioguide_id, member_name, party in senate_members:
            rows.append(dict(
                id=str(ULID()),
                source="senate_xml",
                source_id=source_id,
                congress=119,
                session=1,
                chamber=chamber,
                roll_call=roll_call,
                bill_id=bill_id,
                bill_title=bill_title,
                member_bioguide_id=bioguide_id,
                member_name=member_name,
                position=_position(party, bill_id),
                voted_at=voted_at,
                payload={},
                is_processed=False,
            ))
    return rows


# ── Historical votes for correlation demo ─────────────────────────────────────
#
# Three target pairs with designed before/after patterns:
#
#   REP011  energy_natural_resources  event 2024-10-20
#     before (8 votes): 1 Yea, 7 Nay  → 12.5% aligned
#     after  (7 votes): 6 Yea, 1 Nay  → 85.7% aligned   shift ≈ +0.73
#
#   REP023  finance_insurance_real_estate  event 2024-10-15
#     before (8 votes): 1 Yea, 7 Nay  → 12.5% aligned
#     after  (6 votes): 5 Yea, 1 Nay  → 83.3% aligned   shift ≈ +0.71
#
#   REP019  communications_electronics  event 2024-10-20
#     before (8 votes): 1 Yea, 7 Nay  → 12.5% aligned
#     after  (6 votes): 5 Yea, 1 Nay  → 83.3% aligned   shift ≈ +0.71


def _build_historical_votes() -> list[dict]:
    """
    Generate historical before-window votes (118th Congress, 2022–2024) plus
    supplementary after-window votes (late 2024–2026) for the three demo reps.

    Source IDs use distinct roll-call ranges that do not collide with the
    existing seeds:
      house/118/2/3xx  — REP011 historical (before)
      senate/118/2/5xx — REP023 historical (before)
      senate/118/2/7xx — REP019 historical (before)
      house/118/2/4xx  — REP011 supplementary (after)
      senate/118/2/6xx — REP023 supplementary (after)
      senate/118/2/8xx — REP019 supplementary (after)
    """
    from ulid import ULID

    rows: list[dict] = []

    def _vote(source_id, bill_id, member_bioguide_id, member_name, position,
               voted_at, chamber, congress=118, session_num=2):
        bill = next(
            (b for b in HISTORICAL_BILLS if b["congress_gov_id"] == bill_id),
            None,
        )
        title = bill["title"] if bill else bill_id
        return dict(
            id=str(ULID()),
            source="congress_api" if chamber == "House" else "senate_xml",
            source_id=source_id,
            congress=congress,
            session=session_num,
            chamber=chamber,
            roll_call=int(source_id.split("/")[-1]),
            bill_id=bill_id,
            bill_title=title,
            member_bioguide_id=member_bioguide_id,
            member_name=member_name,
            position=position,
            voted_at=voted_at,
            payload={},
            is_processed=False,
        )

    # ── REP011 (H000011, Bradley J. Harmon, R-TX) + energy ────────────────────
    # BEFORE (energy event = 2024-10-20, window: 2022-10-20 → 2024-10-20)
    # 1 Yea, 7 Nay
    energy_before = [
        ("house/118/2/301", "hr3001", "2022-11-08", "Nay"),
        ("house/118/2/302", "hr3002", "2023-01-25", "Nay"),
        ("house/118/2/303", "hr3003", "2023-04-12", "Nay"),
        ("house/118/2/304", "hr3001", "2023-07-19", "Nay"),
        ("house/118/2/305", "hr3002", "2023-10-30", "Nay"),
        ("house/118/2/306", "hr3003", "2024-02-14", "Yea"),  # one early YES
        ("house/118/2/307", "hr3001", "2024-05-22", "Nay"),
        ("house/118/2/308", "hr3002", "2024-08-07", "Nay"),
    ]
    for src_id, bill_id, voted_at, pos in energy_before:
        rows.append(_vote(src_id, bill_id, "H000011", "Bradley J. Harmon",
                          pos, voted_at, "House"))

    # AFTER (energy event = 2024-10-20, window: 2024-10-20 → 2026-10-20)
    # 6 Yea, 1 Nay (the existing 2025 seed adds hr1010→Yea, hr1001→Nay, so
    # this gives a total after picture of 7 Yea / 2 Nay after combining,
    # but this function just adds the supplementary votes)
    energy_after = [
        ("house/118/2/401", "hr3001", "2024-11-15", "Yea"),
        ("house/118/2/402", "hr3002", "2025-04-22", "Yea"),
        ("house/118/2/403", "hr3003", "2025-06-10", "Yea"),
        ("house/118/2/404", "hr3001", "2025-09-03", "Yea"),
        ("house/118/2/405", "hr3002", "2026-01-14", "Yea"),
        ("house/118/2/406", "hr3003", "2026-03-28", "Yea"),
        ("house/118/2/407", "hr3001", "2026-06-05", "Nay"),  # one late nay
    ]
    for src_id, bill_id, voted_at, pos in energy_after:
        rows.append(_vote(src_id, bill_id, "H000011", "Bradley J. Harmon",
                          pos, voted_at, "House"))

    # ── REP023 (B000023, Randall T. Boone, R-TX) + finance ────────────────────
    # BEFORE (finance event = 2024-10-15, window: 2022-10-15 → 2024-10-15)
    # 1 Yea, 7 Nay
    finance_before = [
        ("senate/118/2/501", "hr3004", "2022-11-10", "Nay"),
        ("senate/118/2/502", "s3001",  "2023-01-18", "Nay"),
        ("senate/118/2/503", "hr3004", "2023-04-05", "Nay"),
        ("senate/118/2/504", "s3001",  "2023-07-12", "Nay"),
        ("senate/118/2/505", "hr3004", "2023-11-08", "Yea"),  # one early YES
        ("senate/118/2/506", "s3001",  "2024-03-20", "Nay"),
        ("senate/118/2/507", "hr3004", "2024-06-14", "Nay"),
        ("senate/118/2/508", "s3001",  "2024-09-03", "Nay"),
    ]
    for src_id, bill_id, voted_at, pos in finance_before:
        rows.append(_vote(src_id, bill_id, "B000023", "Randall T. Boone",
                          pos, voted_at, "Senate"))

    # AFTER: 5 Yea, 1 Nay
    finance_after = [
        ("senate/118/2/601", "hr3004", "2024-11-20", "Yea"),
        ("senate/118/2/602", "s3001",  "2025-02-11", "Yea"),
        ("senate/118/2/603", "hr3004", "2025-05-07", "Yea"),
        ("senate/118/2/604", "s3001",  "2025-08-19", "Yea"),
        ("senate/118/2/605", "hr3004", "2025-11-12", "Yea"),
        ("senate/118/2/606", "s3001",  "2026-02-04", "Nay"),  # one exception
    ]
    for src_id, bill_id, voted_at, pos in finance_after:
        rows.append(_vote(src_id, bill_id, "B000023", "Randall T. Boone",
                          pos, voted_at, "Senate"))

    # ── REP019 (D000019, Eleanor H. Davenport, D-CA) + communications ─────────
    # BEFORE (tech event = 2024-10-20, window: 2022-10-20 → 2024-10-20)
    # 1 Yea, 7 Nay
    tech_before = [
        ("senate/118/2/701", "hr3006", "2022-11-04", "Nay"),
        ("senate/118/2/702", "s3002",  "2023-01-26", "Nay"),
        ("senate/118/2/703", "hr3006", "2023-05-18", "Nay"),
        ("senate/118/2/704", "s3002",  "2023-09-07", "Nay"),
        ("senate/118/2/705", "hr3006", "2024-01-15", "Yea"),  # one early YES
        ("senate/118/2/706", "s3002",  "2024-04-30", "Nay"),
        ("senate/118/2/707", "hr3006", "2024-07-11", "Nay"),
        ("senate/118/2/708", "s3002",  "2024-09-25", "Nay"),
    ]
    for src_id, bill_id, voted_at, pos in tech_before:
        rows.append(_vote(src_id, bill_id, "D000019", "Eleanor H. Davenport",
                          pos, voted_at, "Senate"))

    # AFTER: 5 Yea, 1 Nay
    tech_after = [
        ("senate/118/2/801", "hr3006", "2024-11-12", "Yea"),
        ("senate/118/2/802", "s3002",  "2025-02-25", "Yea"),
        ("senate/118/2/803", "hr3006", "2025-05-14", "Yea"),
        ("senate/118/2/804", "s3002",  "2025-08-06", "Yea"),
        ("senate/118/2/805", "hr3006", "2025-11-19", "Yea"),
        ("senate/118/2/806", "s3002",  "2026-02-04", "Nay"),  # one exception
    ]
    for src_id, bill_id, voted_at, pos in tech_after:
        rows.append(_vote(src_id, bill_id, "D000019", "Eleanor H. Davenport",
                          pos, voted_at, "Senate"))

    return rows


# ── Helpers ────────────────────────────────────────────────────────────────────


def _rel_id(donor_id: str, rep_id: str) -> str:
    return f"REL_{donor_id}_{rep_id}"


def _create_tables() -> None:
    log.info("Creating tables if they don't exist…")
    Base.metadata.create_all(engine)


def _reset(session) -> None:
    log.info("Resetting seed rows…")
    rel_ids = [_rel_id(d, r) for d, r, *_ in RELATIONSHIPS]
    rep_ids = [r["id"] for r in REPS]
    donor_ids = [d["id"] for d in DONORS]
    bill_ids = [b["id"] for b in BILLS] + [b["id"] for b in HISTORICAL_BILLS]
    if rel_ids:
        session.execute(
            text("DELETE FROM canonical_donor_rep_relationships WHERE id = ANY(:ids)"),
            {"ids": rel_ids},
        )
    # Alignment scores reference reps — delete before reps
    if rep_ids:
        session.execute(
            text("DELETE FROM alignment_scores WHERE rep_id = ANY(:ids)"),
            {"ids": rep_ids},
        )
        session.execute(
            text("DELETE FROM correlation_events WHERE rep_id = ANY(:ids)"),
            {"ids": rep_ids},
        )
        session.execute(
            text("DELETE FROM canonical_reps WHERE id = ANY(:ids)"),
            {"ids": rep_ids},
        )
    if donor_ids:
        session.execute(
            text("DELETE FROM canonical_donors WHERE id = ANY(:ids)"),
            {"ids": donor_ids},
        )
    # Delete raw_votes by source pattern and bills by id
    session.execute(
        text(
            "DELETE FROM raw_votes WHERE source_id LIKE 'house/119/1/%'"
            " OR source_id LIKE 'senate/119/1/%'"
            " OR source_id LIKE 'house/118/2/%'"
            " OR source_id LIKE 'senate/118/2/%'"
        ),
    )
    if bill_ids:
        session.execute(
            text("DELETE FROM bills WHERE id = ANY(:ids)"),
            {"ids": bill_ids},
        )


def _seed_postgres(session) -> None:
    # Representatives
    inserted_reps = 0
    for r in REPS:
        existing = session.get(CanonicalRepRow, r["id"])
        if existing:
            continue
        session.add(CanonicalRepRow(**r))
        inserted_reps += 1
    log.info(f"  Representatives: {inserted_reps} inserted ({len(REPS) - inserted_reps} already existed)")

    # Donors
    inserted_donors = 0
    for d in DONORS:
        existing = session.get(CanonicalDonorRow, d["id"])
        if existing:
            continue
        session.add(CanonicalDonorRow(**d))
        inserted_donors += 1
    log.info(f"  Donors: {inserted_donors} inserted ({len(DONORS) - inserted_donors} already existed)")

    session.flush()  # ensure FK constraints resolve before relationships

    # Relationships
    inserted_rels = 0
    for donor_id, rep_id, total_cents, cycles, first_date, latest_date in RELATIONSHIPS:
        rel_id = _rel_id(donor_id, rep_id)
        existing = session.get(CanonicalRelationshipRow, rel_id)
        if existing:
            continue
        session.add(CanonicalRelationshipRow(
            id=rel_id,
            donor_id=donor_id,
            rep_id=rep_id,
            total_amount_cents=total_cents,
            contribution_count=len(cycles),
            first_donation_date=first_date,
            latest_donation_date=latest_date,
            election_cycles=json.dumps(cycles),
        ))
        inserted_rels += 1
    log.info(f"  Relationships: {inserted_rels} inserted ({len(RELATIONSHIPS) - inserted_rels} already existed)")

    # Bills (Sprint 7)
    inserted_bills = 0
    for b in BILLS:
        existing = session.get(BillRow, b["id"])
        if existing:
            continue
        session.add(BillRow(**b))
        inserted_bills += 1
    log.info(f"  Bills: {inserted_bills} inserted ({len(BILLS) - inserted_bills} already existed)")
    session.flush()

    # Raw votes (Sprint 7 — 2025 votes)
    vote_rows = _build_votes()
    inserted_votes = 0
    for v in vote_rows:
        existing = session.execute(
            text("SELECT 1 FROM raw_votes WHERE source_id = :sid AND member_bioguide_id = :bio"),
            {"sid": v["source_id"], "bio": v["member_bioguide_id"]},
        ).fetchone()
        if existing:
            continue
        session.add(RawVoteRow(**v))
        inserted_votes += 1
    log.info(f"  Votes (2025): {inserted_votes} inserted ({len(vote_rows) - inserted_votes} already existed)")

    # Historical bills (118th Congress, Sprint 8 correlation demo)
    inserted_hist_bills = 0
    for b in HISTORICAL_BILLS:
        existing = session.get(BillRow, b["id"])
        if existing:
            continue
        session.add(BillRow(**b))
        inserted_hist_bills += 1
    log.info(f"  Historical bills: {inserted_hist_bills} inserted ({len(HISTORICAL_BILLS) - inserted_hist_bills} already existed)")
    session.flush()

    # Historical votes (2022-2024 before-window + supplementary after-window)
    hist_vote_rows = _build_historical_votes()
    inserted_hist_votes = 0
    for v in hist_vote_rows:
        existing = session.execute(
            text("SELECT 1 FROM raw_votes WHERE source_id = :sid AND member_bioguide_id = :bio"),
            {"sid": v["source_id"], "bio": v["member_bioguide_id"]},
        ).fetchone()
        if existing:
            continue
        session.add(RawVoteRow(**v))
        inserted_hist_votes += 1
    log.info(f"  Historical votes: {inserted_hist_votes} inserted ({len(hist_vote_rows) - inserted_hist_votes} already existed)")


def _seed_alignment_scores() -> None:
    """
    Run the correlation engine on the three demo reps and persist results.

    Calls pipeline.tasks.compute_correlations._compute_for_rep() directly
    (no Celery required) so alignment scores appear immediately in the UI.
    """
    from adapters.postgres.orm_models import CanonicalRepRow
    from infrastructure.database import get_session
    from pipeline.tasks.compute_correlations import _compute_for_rep

    demo_rep_ids = {
        "REP011": "Bradley J. Harmon (energy)",
        "REP023": "Randall T. Boone (finance)",
        "REP019": "Eleanor H. Davenport (tech)",
    }

    try:
        with get_session() as session:
            reps = {
                r.id: r
                for r in session.query(CanonicalRepRow)
                .filter(CanonicalRepRow.id.in_(demo_rep_ids.keys()))
                .all()
            }

        total = 0
        for rep_id, label in demo_rep_ids.items():
            rep_row = reps.get(rep_id)
            if rep_row is None:
                log.warning(f"  Alignment: {rep_id} not found in DB, skipping")
                continue
            scores = _compute_for_rep(rep_row)
            total += scores
            log.info(f"  Alignment: {label} → {scores} score(s) written")

        log.info(f"  Alignment scores total: {total} written")
    except Exception as exc:
        log.warning(f"  Alignment score computation failed (non-fatal): {exc}")


def _seed_neo4j() -> None:
    """Write nodes + edges to Neo4j. Skipped gracefully if Neo4j is unreachable."""
    try:
        from adapters.neo4j.relationship_repo import Neo4jRelationshipRepo
        repo = Neo4jRelationshipRepo()

        log.info("  Upserting Neo4j rep nodes…")
        rep_map = {r["id"]: r for r in REPS}
        for r in REPS:
            repo.upsert_rep_node(
                rep_id=r["id"],
                bioguide_id=r.get("bioguide_id"),
                full_name=r["full_name"],
                party=r["party"],
                chamber=r["chamber"],
                state=r["state"],
            )

        log.info("  Upserting Neo4j donor nodes…")
        for d in DONORS:
            repo.upsert_donor_node(
                donor_id=d["id"],
                name=d["name"],
                donor_type=d["donor_type"],
            )

        log.info("  Upserting Neo4j FUNDED edges…")
        for donor_id, rep_id, total_cents, cycles, *_ in RELATIONSHIPS:
            repo.upsert_funded_relationship(
                donor_id=donor_id,
                rep_id=rep_id,
                total_cents=total_cents,
                cycles=cycles,
            )

        log.info(f"  Neo4j: {len(REPS)} rep nodes, {len(DONORS)} donor nodes, {len(RELATIONSHIPS)} edges")

    except Exception as exc:
        log.warning(f"  Neo4j seed skipped (not connected?): {exc}")


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed development database")
    parser.add_argument("--reset", action="store_true", help="Delete existing seed rows before inserting")
    args = parser.parse_args()

    _create_tables()

    log.info("\nSeeding PostgreSQL…")
    with get_session() as session:
        if args.reset:
            _reset(session)
            session.flush()
        _seed_postgres(session)

    log.info("\nComputing alignment scores…")
    _seed_alignment_scores()

    log.info("\nSeeding Neo4j…")
    _seed_neo4j()

    vote_count = len(_build_votes())
    hist_vote_count = len(_build_historical_votes())
    log.info("\nDone. Summary:")
    log.info(f"  {len(REPS)} representatives")
    log.info(f"  {len(DONORS)} donors")
    log.info(f"  {len(RELATIONSHIPS)} funding relationships")
    log.info(f"  {len(BILLS) + len(HISTORICAL_BILLS)} bills ({len(BILLS)} current + {len(HISTORICAL_BILLS)} historical)")
    log.info(f"  {vote_count + hist_vote_count} raw vote records ({vote_count} current + {hist_vote_count} historical)")
    log.info(f"  3 alignment scores (REP011/energy, REP023/finance, REP019/tech)")
    log.info("\nOpen http://localhost:3000 to view the UI.")
    log.info("  Try: /rep/REP011  /rep/REP023  /rep/REP019  (correlation tab populated)")


if __name__ == "__main__":
    main()
