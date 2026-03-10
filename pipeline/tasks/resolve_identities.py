"""
Stage 2: Resolve raw ingestion records to canonical entities.

Steps:
  1. Seed canonical_reps from Congress.gov /member endpoint (both chambers).
  2. Build lis_bioguide_map so Senate raw_votes link to canonical reps.
  3. Deduplicate raw FEC donor names with rapidfuzz → canonical_donors.
  4. Mark processed raw_filings as is_processed=True.

Failure mode: FAIL LOUD — same retry/alert pattern as ingest tasks.
"""

from __future__ import annotations

import logging

from adapters.external.congress_client import CongressApiError, CongressGovClient
from adapters.nlp.entity_resolver import DonorNameResolver
from adapters.postgres.identity_repo import PostgresIdentityRepository
from adapters.postgres.orm_models import RawFilingRow
from domain.identity.services import EntityResolver
from infrastructure.config import get_settings
from infrastructure.database import get_session
from pipeline.celery_app import celery_app
from pipeline.monitoring.alerting import send_pipeline_failure_alert, send_pipeline_success_alert
from pipeline.monitoring.staleness_tracker import StalenessTracker

logger = logging.getLogger(__name__)


@celery_app.task(
    name="pipeline.tasks.resolve_identities.run",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run(self) -> dict:
    """
    Resolve raw ingestion data to canonical entities.

    Returns {"reps_seeded": N, "donors_resolved": N, "filings_marked": N}.
    """
    settings = get_settings()
    congress = settings.current_congress

    logger.info("resolve_identities: starting for congress %d", congress)

    try:
        reps_seeded = _seed_canonical_reps(congress)
        donors_resolved, filings_marked = _resolve_donors()
    except Exception as exc:
        logger.exception("resolve_identities: error on attempt %d: %s", self.request.retries + 1, exc)
        try:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            send_pipeline_failure_alert(
                "resolve_identities", exc, extra={"congress": congress}
            )
            raise

    StalenessTracker().record_success()
    send_pipeline_success_alert(
        "resolve_identities", rows_written=reps_seeded + donors_resolved
    )
    logger.info(
        "resolve_identities: done — %d reps, %d donors, %d filings marked",
        reps_seeded, donors_resolved, filings_marked,
    )
    return {
        "reps_seeded": reps_seeded,
        "donors_resolved": donors_resolved,
        "filings_marked": filings_marked,
    }


# ── Step 1: Seed canonical_reps from Congress.gov ─────────────────────────────


def _seed_canonical_reps(congress: int) -> int:
    """
    Fetch all House and Senate members from Congress.gov and upsert into
    canonical_reps. Also populates lis_bioguide_map for Senate members.

    Returns number of reps newly created (not updated).
    """
    reps_created = 0

    with CongressGovClient() as api:
        with get_session() as session:
            repo = PostgresIdentityRepository(session)
            resolver = EntityResolver(repo)

            for chamber in ("House", "Senate"):
                for member in api.get_members(congress=congress, chamber=chamber):
                    bioguide_id = member.get("bioguideId", "")
                    if not bioguide_id:
                        continue

                    terms = member.get("terms", {}).get("item", [])
                    latest_term = terms[-1] if terms else {}

                    full_name = (
                        member.get("name")
                        or f"{member.get('firstName', '')} {member.get('lastName', '')}".strip()
                    )
                    party = _extract_party(member, latest_term)
                    state = member.get("state", latest_term.get("stateCode", ""))[:2]
                    district = _extract_district(member, latest_term, chamber)

                    existing = repo.find_rep_by_bioguide_id(bioguide_id)
                    if existing is None:
                        resolver.resolve_rep_from_bioguide(
                            bioguide_id=bioguide_id,
                            full_name=full_name,
                            party=party,
                            chamber=chamber,
                            state=state,
                            district=district,
                        )
                        reps_created += 1

            session.commit()

    logger.info("resolve_identities: seeded %d canonical reps", reps_created)
    return reps_created


# ── Step 2: Build lis_bioguide_map ────────────────────────────────────────────


def _build_lis_map(congress: int) -> None:
    """
    Fetch Senate members and map their LIS IDs to bioguide_ids.

    The Senate XML feed uses lis_member_id (e.g. "S001") which is different
    from the Congress.gov bioguide_id (e.g. "A000370"). This mapping table
    allows Senate raw_votes to be linked to canonical_reps during Sprint 4.

    Note: Congress.gov does not expose lis_member_id directly. We derive it
    from the Senate.gov member list XML, which does include both IDs.
    This step is best-effort; unresolved LIS IDs remain in raw_votes until
    manually reconciled.
    """
    # TODO Sprint 3 (follow-up): fetch Senate member list from Senate.gov XML
    # to obtain lis_member_id → bioguide_id mapping. The Congress.gov API
    # does not expose LIS IDs. For now, raw Senate votes link via member name
    # matching during Sprint 4 aggregation.
    pass


# ── Step 3: Resolve donors ────────────────────────────────────────────────────


def _resolve_donors() -> tuple[int, int]:
    """
    Read all unprocessed raw_filings, cluster donor names with rapidfuzz,
    upsert canonical_donors, and mark filings as processed.

    Returns (donors_resolved, filings_marked).
    """
    with get_session() as session:
        unprocessed: list[RawFilingRow] = (
            session.query(RawFilingRow)
            .filter_by(is_processed=False)
            .all()
        )

    if not unprocessed:
        logger.info("resolve_identities: no unprocessed filings")
        return 0, 0

    logger.info("resolve_identities: resolving %d unprocessed filings", len(unprocessed))

    # Phase 1: cluster all donor names with rapidfuzz
    name_resolver = DonorNameResolver()
    for filing in unprocessed:
        name_resolver.add(filing.contributor_name, fec_id=filing.committee_id)

    clusters = name_resolver.clusters
    logger.info("resolve_identities: %d name clusters from %d filings", len(clusters), len(unprocessed))

    # Phase 2: upsert canonical_donors and mark filings processed
    donors_created = 0
    with get_session() as session:
        repo = PostgresIdentityRepository(session)
        resolver = EntityResolver(repo)

        for cluster in clusters:
            # Use the first FEC ID as the primary key for lookup
            primary_fec_id = cluster.fec_ids[0] if cluster.fec_ids else ""
            donor = resolver.resolve_donor(
                canonical_name=cluster.canonical_name,
                donor_type="individual",   # refined in Sprint 7 via FEC committee lookup
                fec_id=primary_fec_id,
            )
            donors_created += 1

            # Merge any additional FEC IDs into this canonical donor
            for extra_fec_id in cluster.fec_ids[1:]:
                resolver.merge_donor_fec_id(donor, extra_fec_id)

        # Mark filings as processed
        filing_ids = [f.id for f in unprocessed]
        session.query(RawFilingRow).filter(
            RawFilingRow.id.in_(filing_ids)
        ).update({"is_processed": True}, synchronize_session=False)
        session.commit()

    return donors_created, len(unprocessed)


# ── Field extraction helpers ──────────────────────────────────────────────────


def _extract_party(member: dict, latest_term: dict) -> str:
    return (
        member.get("partyName", "")[:1]
        or member.get("party", "")[:1]
        or latest_term.get("partyCode", "")[:1]
        or "O"
    )


def _extract_district(member: dict, latest_term: dict, chamber: str) -> str | None:
    if chamber.lower() == "senate":
        return None
    district_num = member.get("district") or latest_term.get("district")
    state = member.get("state", latest_term.get("stateCode", ""))[:2]
    if district_num and state:
        return f"{state}-{district_num:02d}" if isinstance(district_num, int) else f"{state}-{district_num}"
    return None
