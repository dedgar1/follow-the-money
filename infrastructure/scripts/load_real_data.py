"""
Load real data without Celery — for local dev testing.

Runs the full pipeline (ingest → identity → classify → finance → correlations)
with scope limits so a small but realistic dataset is loaded quickly.

Usage examples:

  # All Senate members, up to 200 FEC contributions per rep
  uv run infrastructure/scripts/load_real_data.py --chamber senate

  # Senate only, single state
  uv run infrastructure/scripts/load_real_data.py --chamber senate --state CA

  # House + Senate, capped at 20 reps total, 100 contributions each
  uv run infrastructure/scripts/load_real_data.py --reps 20 --contributions 100

  # Skip expensive vote ingest if you just want finance data
  uv run infrastructure/scripts/load_real_data.py --chamber senate --skip-votes

  # Skip FEC if canonical reps + committees are already seeded
  uv run infrastructure/scripts/load_real_data.py --skip-fec --skip-votes
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure the project root is on sys.path when run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("load_real_data")


# ── CLI ───────────────────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--chamber", choices=["house", "senate", "both"], default="both",
                   help="Which chamber(s) to load Congress members for (default: both)")
    p.add_argument("--state", metavar="XX",
                   help="Filter to a single state, e.g. CA (optional)")
    p.add_argument("--reps", type=int, default=0, metavar="N",
                   help="Max canonical reps to process (0 = unlimited)")
    p.add_argument("--contributions", type=int, default=200, metavar="N",
                   help="Max FEC contributions to fetch per rep committee (default: 200)")
    p.add_argument("--cycle", type=int, default=0, metavar="YYYY",
                   help="FEC election cycle year, e.g. 2024 (default: derived from config)")
    p.add_argument("--congress", type=int, default=0, metavar="N",
                   help="Congress number, e.g. 119 (default: from config)")
    p.add_argument("--session", type=int, default=0, metavar="N",
                   help="Congressional session number (default: from config)")
    p.add_argument("--skip-fec", action="store_true",
                   help="Skip FEC contribution ingestion (reps still seeded)")
    p.add_argument("--skip-votes", action="store_true",
                   help="Skip vote ingestion and bill classification")
    return p.parse_args()


# ── Step 1: Seed canonical reps (filtered) ────────────────────────────────────


def seed_reps(congress: int, chambers: list[str], state_filter: str | None, rep_limit: int) -> list[str]:
    """
    Seed canonical_reps from Congress.gov for the requested chamber(s).
    Returns list of canonical rep IDs that were created or already exist.
    """
    from adapters.external.congress_client import CongressGovClient
    from adapters.postgres.identity_repo import PostgresIdentityRepository
    from adapters.postgres.orm_models import CanonicalRepRow
    from domain.identity.services import EntityResolver
    from infrastructure.database import get_session
    from pipeline.tasks.resolve_identities import _extract_party, _extract_district

    logger.info("Step 1 — seeding canonical reps (congress=%d, chambers=%s, state=%s)",
                congress, chambers, state_filter or "all")

    created = 0
    rep_ids: list[str] = []

    with CongressGovClient() as api:
        with get_session() as session:
            repo = PostgresIdentityRepository(session)
            resolver = EntityResolver(repo)

            for chamber in chambers:
                chamber_label = chamber.capitalize()
                logger.info("  Fetching %s members from Congress.gov…", chamber_label)

                for member in api.get_members(congress=congress, chamber=chamber_label):
                    bioguide_id = member.get("bioguideId", "")
                    if not bioguide_id:
                        continue

                    member_state = member.get("state", "")[:2].upper()
                    if state_filter and member_state != state_filter.upper():
                        continue

                    terms = member.get("terms", {}).get("item", [])
                    latest_term = terms[-1] if terms else {}

                    full_name = (
                        member.get("name")
                        or f"{member.get('firstName', '')} {member.get('lastName', '')}".strip()
                    )
                    party = _extract_party(member, latest_term)
                    state = member_state or member.get("state", latest_term.get("stateCode", ""))[:2]
                    district = _extract_district(member, latest_term, chamber_label)

                    existing = repo.find_rep_by_bioguide_id(bioguide_id)
                    if existing is None:
                        resolved = resolver.resolve_rep_from_bioguide(
                            bioguide_id=bioguide_id,
                            full_name=full_name,
                            party=party,
                            chamber=chamber_label,
                            state=state,
                            district=district,
                        )
                        rep_ids.append(str(resolved.id))
                        created += 1
                    else:
                        rep_ids.append(str(existing.id))

                    if rep_limit and len(rep_ids) >= rep_limit:
                        logger.info("  Hit --reps limit (%d); stopping member fetch", rep_limit)
                        break

                session.commit()

                if rep_limit and len(rep_ids) >= rep_limit:
                    break

    # Load all canonical rep IDs if we didn't hit the limit (handles re-runs)
    if not rep_ids:
        with get_session() as session:
            rows = session.query(CanonicalRepRow).all()
            rep_ids = [r.id for r in rows]

    logger.info("Step 1 done — %d new reps seeded, %d total in scope", created, len(rep_ids))
    return rep_ids


# ── Step 2: Ingest FEC contributions ─────────────────────────────────────────


def ingest_fec(rep_ids: list[str], cycle: int, max_per_committee: int) -> int:
    """
    For each canonical rep with a FEC candidate ID, fetch their committees,
    then fetch up to max_per_committee contributions per committee.
    Returns total raw_filings rows written.
    """
    from adapters.external.fec_client import FECApiClient, FECApiError
    from adapters.postgres.orm_models import CanonicalRepRow, FecCommitteeCandidateRow, RawFilingRow
    from infrastructure.database import get_session
    from pipeline.tasks.ingest_fec import _map_to_domain, _to_row_dict, _upsert_batch
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    logger.info("Step 2 — FEC contributions (cycle=%d, max_per_committee=%d)", cycle, max_per_committee)

    # Load reps with FEC candidate IDs
    with get_session() as session:
        rep_rows = (
            session.query(CanonicalRepRow)
            .filter(CanonicalRepRow.id.in_(rep_ids), CanonicalRepRow.fec_candidate_id.isnot(None))
            .all()
        )
        reps_with_fec = [(r.id, r.full_name, r.fec_candidate_id) for r in rep_rows]

    logger.info("  %d of %d reps have FEC candidate IDs", len(reps_with_fec), len(rep_ids))

    if not reps_with_fec:
        logger.warning("  No reps with FEC IDs — skipping FEC ingest. "
                       "This is normal for a fresh seed; run again after Congress.gov populates fec_candidate_id.")
        return 0

    total_written = 0

    with FECApiClient() as fec:
        for _rep_id, rep_name, candidate_id in reps_with_fec:
            try:
                committees = fec.get_committees_for_candidate(candidate_id)
            except FECApiError as exc:
                logger.warning("  Could not fetch committees for %s (%s): %s", rep_name, candidate_id, exc)
                continue

            committee_ids = [c["id"] for c in committees if c.get("id")]
            if not committee_ids:
                logger.debug("  %s — no committees found", rep_name)
                continue

            rep_rows_written = 0
            for cid in committee_ids:
                # Store committee → candidate mapping
                with get_session() as session:
                    stmt = pg_insert(FecCommitteeCandidateRow).values({
                        "committee_id": cid,
                        "fec_candidate_id": candidate_id,
                        "committee_name": next(
                            (c.get("name") for c in committees if c.get("id") == cid), None
                        ),
                    })
                    stmt = stmt.on_conflict_do_nothing(index_elements=["committee_id"])
                    session.execute(stmt)
                    session.commit()

                # Fetch contributions for this committee, up to the cap
                batch: list[dict] = []
                fetched = 0
                try:
                    with get_session() as session:
                        for record in fec.get_contributions(
                            committee_id=cid,
                            two_year_transaction_period=cycle,
                        ):
                            filing = _map_to_domain(record)
                            batch.append(_to_row_dict(filing))
                            fetched += 1

                            if len(batch) >= 100:
                                rep_rows_written += _upsert_batch(session, RawFilingRow, batch)
                                batch.clear()

                            if fetched >= max_per_committee:
                                break

                        if batch:
                            rep_rows_written += _upsert_batch(session, RawFilingRow, batch)

                except FECApiError as exc:
                    logger.warning("  FEC contributions error for committee %s: %s", cid, exc)

            if rep_rows_written:
                logger.info("  %s — %d filings", rep_name, rep_rows_written)
            total_written += rep_rows_written

    logger.info("Step 2 done — %d raw_filings written", total_written)
    return total_written


# ── Step 3: Ingest votes ──────────────────────────────────────────────────────


def ingest_votes(congress: int, session_num: int, chambers: list[str]) -> int:
    """
    Fetch roll-call votes for the requested chamber(s).
    Returns rows written.
    """
    from pipeline.tasks.ingest_votes import _ingest_house, _ingest_senate

    logger.info("Step 3 — ingesting votes (congress=%d, session=%d, chambers=%s)",
                congress, session_num, chambers)

    total = 0
    if "house" in chambers:
        logger.info("  Fetching House votes…")
        try:
            n = _ingest_house(congress, session_num)
            logger.info("  House: %d vote rows", n)
            total += n
        except Exception as exc:
            logger.warning("  House vote ingest failed: %s", exc)

    if "senate" in chambers:
        logger.info("  Fetching Senate votes…")
        try:
            n = _ingest_senate(congress, session_num)
            logger.info("  Senate: %d vote rows", n)
            total += n
        except Exception as exc:
            logger.warning("  Senate vote ingest failed: %s", exc)

    logger.info("Step 3 done — %d raw_votes written", total)
    return total


# ── Step 4: Classify bills ────────────────────────────────────────────────────


def classify_bills() -> int:
    from pipeline.tasks.classify_bills import _classify_all_bills
    logger.info("Step 4 — classifying bills with NLP…")
    n = _classify_all_bills()
    logger.info("Step 4 done — %d bills classified", n)
    return n


# ── Step 5: Resolve donor identities ─────────────────────────────────────────


def resolve_donors() -> tuple[int, int]:
    from pipeline.tasks.resolve_identities import _resolve_donors
    logger.info("Step 5 — resolving donor identities (rapidfuzz clustering)…")
    donors, filings = _resolve_donors()
    logger.info("Step 5 done — %d canonical donors, %d filings marked", donors, filings)
    return donors, filings


# ── Step 6: Aggregate finance ─────────────────────────────────────────────────


def aggregate_finance() -> tuple[int, int]:
    from pipeline.tasks.aggregate_finance import _aggregate
    logger.info("Step 6 — aggregating finance relationships…")
    relationships, neo4j_edges = _aggregate()
    logger.info("Step 6 done — %d relationships, %d Neo4j edges", relationships, neo4j_edges)
    return relationships, neo4j_edges


# ── Step 7: Compute correlations ─────────────────────────────────────────────


def compute_correlations() -> int:
    from pipeline.tasks.compute_correlations import _compute_all
    logger.info("Step 7 — computing alignment scores…")
    scores = _compute_all()
    logger.info("Step 7 done — %d alignment scores written", scores)
    return scores


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    args = _parse_args()

    from infrastructure.config import get_settings
    settings = get_settings()

    congress = args.congress or settings.current_congress
    session_num = args.session or settings.current_session
    cycle = args.cycle or (1786 + congress * 2)  # e.g. 119 → 2024

    chambers: list[str]
    if args.chamber == "both":
        chambers = ["house", "senate"]
    else:
        chambers = [args.chamber]

    logger.info("=" * 60)
    logger.info("load_real_data — congress=%d  session=%d  cycle=%d", congress, session_num, cycle)
    logger.info("  chambers: %s  |  state: %s  |  reps_cap: %s  |  contribs_cap: %d",
                chambers, args.state or "all", args.reps or "unlimited", args.contributions)
    logger.info("  skip_fec=%s  skip_votes=%s", args.skip_fec, args.skip_votes)
    logger.info("=" * 60)

    # 1. Seed reps
    rep_ids = seed_reps(congress, chambers, args.state, args.reps)

    # 2. FEC contributions
    if not args.skip_fec:
        ingest_fec(rep_ids, cycle, args.contributions)
    else:
        logger.info("Step 2 — skipped (--skip-fec)")

    # 3. Votes
    if not args.skip_votes:
        ingest_votes(congress, session_num, chambers)
        classify_bills()
    else:
        logger.info("Steps 3–4 — skipped (--skip-votes)")

    # 5. Resolve donors
    resolve_donors()

    # 6. Aggregate
    aggregate_finance()

    # 7. Correlations
    compute_correlations()

    logger.info("=" * 60)
    logger.info("Done! Visit http://localhost:3000 to explore real data.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
