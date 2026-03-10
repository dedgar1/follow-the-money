"""Add finance aggregation tables: fec_committee_candidates, canonical_donor_rep_relationships.
Also adds canonical_donor_id FK to raw_filings.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-10

fec_committee_candidates: maps FEC committee_id → principal candidate_id so
  aggregate_finance can link raw filings to canonical reps.

canonical_donor_rep_relationships: aggregate root for the Finance context —
  total contributions, date range, and election cycles per (donor, rep) pair.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Committee → candidate mapping table
    op.create_table(
        "fec_committee_candidates",
        sa.Column("committee_id", sa.String(20), primary_key=True),
        sa.Column("fec_candidate_id", sa.String(20), nullable=True),
        sa.Column("committee_name", sa.String(500), nullable=True),
        sa.Column("fetched_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_fec_committee_candidates_fec_candidate_id",
        "fec_committee_candidates",
        ["fec_candidate_id"],
    )

    # Canonical aggregate relationship table
    op.create_table(
        "canonical_donor_rep_relationships",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("donor_id", sa.String(26), nullable=False),
        sa.Column("rep_id", sa.String(26), nullable=False),
        sa.Column("total_amount_cents", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("contribution_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("first_donation_date", sa.String(10), nullable=True),
        sa.Column("latest_donation_date", sa.String(10), nullable=True),
        sa.Column("election_cycles", sa.Text, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["donor_id"], ["canonical_donors.id"], name="fk_cdr_donor_id"),
        sa.ForeignKeyConstraint(["rep_id"], ["canonical_reps.id"], name="fk_cdr_rep_id"),
    )
    op.create_index("ix_canonical_rel_donor_id", "canonical_donor_rep_relationships", ["donor_id"])
    op.create_index("ix_canonical_rel_rep_id", "canonical_donor_rep_relationships", ["rep_id"])
    op.create_index(
        "uq_canonical_rel_donor_rep",
        "canonical_donor_rep_relationships",
        ["donor_id", "rep_id"],
        unique=True,
    )

    # Add canonical_donor_id FK to raw_filings
    op.add_column(
        "raw_filings",
        sa.Column("canonical_donor_id", sa.String(26), nullable=True),
    )
    op.create_foreign_key(
        "fk_raw_filings_canonical_donor_id",
        "raw_filings",
        "canonical_donors",
        ["canonical_donor_id"],
        ["id"],
    )
    op.create_index("ix_raw_filings_canonical_donor_id", "raw_filings", ["canonical_donor_id"])


def downgrade() -> None:
    op.drop_index("ix_raw_filings_canonical_donor_id", table_name="raw_filings")
    op.drop_constraint("fk_raw_filings_canonical_donor_id", "raw_filings", type_="foreignkey")
    op.drop_column("raw_filings", "canonical_donor_id")
    op.drop_table("canonical_donor_rep_relationships")
    op.drop_table("fec_committee_candidates")
