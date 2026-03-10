"""Add canonical identity tables: canonical_reps, canonical_donors, lis_bioguide_map

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-10

canonical_reps and canonical_donors are the resolved, deduplicated entities
produced by the identity resolution pipeline (Sprint 3).

lis_bioguide_map resolves Senate LIS member IDs (from Senate.gov XML) to
Congress.gov bioguide_ids so Senate raw_votes can link to canonical_reps.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "canonical_reps",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("full_name", sa.String(500), nullable=False),
        sa.Column("party", sa.String(1), nullable=False),          # "D" | "R" | "I" | "O"
        sa.Column("chamber", sa.String(10), nullable=False),        # "house" | "senate"
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("district", sa.String(10), nullable=True),        # e.g. "CA-12"
        sa.Column("bioguide_id", sa.String(20), nullable=True, unique=True),
        sa.Column("fec_candidate_id", sa.String(20), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_canonical_reps_state", "canonical_reps", ["state"])
    op.create_index("ix_canonical_reps_chamber", "canonical_reps", ["chamber"])
    op.create_index("ix_canonical_reps_party", "canonical_reps", ["party"])

    op.create_table(
        "canonical_donors",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("donor_type", sa.String(20), nullable=False),     # "individual" | "pac" etc.
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("fec_ids", sa.Text, nullable=False, server_default="[]"),  # JSON array
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_canonical_donors_name", "canonical_donors", ["name"])
    op.create_index("ix_canonical_donors_donor_type", "canonical_donors", ["donor_type"])
    op.create_index("ix_canonical_donors_industry", "canonical_donors", ["industry"])

    # Maps Senate LIS member IDs → Congress.gov bioguide_ids.
    # Populated during identity resolution by calling Congress.gov /member endpoint.
    op.create_table(
        "lis_bioguide_map",
        sa.Column("lis_member_id", sa.String(20), primary_key=True),
        sa.Column("bioguide_id", sa.String(20), nullable=False),
        sa.Column("full_name", sa.String(500), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("party", sa.String(1), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["bioguide_id"],
            ["canonical_reps.bioguide_id"],
            name="fk_lis_bioguide_map_bioguide_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_lis_bioguide_map_bioguide_id", "lis_bioguide_map", ["bioguide_id"])


def downgrade() -> None:
    op.drop_table("lis_bioguide_map")
    op.drop_table("canonical_donors")
    op.drop_table("canonical_reps")
