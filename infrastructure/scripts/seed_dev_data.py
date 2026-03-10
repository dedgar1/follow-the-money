"""
Seed development database with realistic sample data.

Creates:
  - 25 canonical representatives (House + Senate, D/R/I, various states)
  - 12 canonical donors (PACs, corporations, unions across key industries)
  - ~60 funding relationships with realistic donation amounts
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
    Base,
    CanonicalDonorRow,
    CanonicalRelationshipRow,
    CanonicalRepRow,
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
    if rel_ids:
        session.execute(
            text("DELETE FROM canonical_donor_rep_relationships WHERE id = ANY(:ids)"),
            {"ids": rel_ids},
        )
    if rep_ids:
        session.execute(
            text("DELETE FROM canonical_reps WHERE id = ANY(:ids)"),
            {"ids": rep_ids},
        )
    if donor_ids:
        session.execute(
            text("DELETE FROM canonical_donors WHERE id = ANY(:ids)"),
            {"ids": donor_ids},
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

    log.info("\nSeeding Neo4j…")
    _seed_neo4j()

    log.info("\nDone. Summary:")
    log.info(f"  {len(REPS)} representatives")
    log.info(f"  {len(DONORS)} donors")
    log.info(f"  {len(RELATIONSHIPS)} funding relationships")
    log.info("\nOpen http://localhost:3000 to view the UI.")


if __name__ == "__main__":
    main()
