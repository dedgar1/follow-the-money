"""Initial schema: representatives, donors, contributions, relationships, bills, votes

Revision ID: 0001
Revises:
Create Date: 2026-03-09
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "representatives",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("party", sa.String(1), nullable=False),
        sa.Column("chamber", sa.String(10), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("district", sa.String(10), nullable=True),
        sa.Column("bioguide_id", sa.String(20), nullable=True, unique=True),
        sa.Column("fec_candidate_id", sa.String(20), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_representatives_state", "representatives", ["state"])
    op.create_index("ix_representatives_party", "representatives", ["party"])
    op.create_index("ix_representatives_chamber", "representatives", ["chamber"])

    op.create_table(
        "donors",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("donor_type", sa.String(20), nullable=False),
        sa.Column("industry", sa.String(50), nullable=True),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_donors_industry", "donors", ["industry"])

    op.create_table(
        "contributions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("donor_id", sa.String(26), sa.ForeignKey("donors.id"), nullable=False),
        sa.Column(
            "representative_id",
            sa.String(26),
            sa.ForeignKey("representatives.id"),
            nullable=False,
        ),
        sa.Column("amount_cents", sa.BigInteger, nullable=False),
        sa.Column("contributed_on", sa.Date, nullable=False),
        sa.Column("election_cycle", sa.Integer, nullable=False),
        sa.Column("contribution_type", sa.String(20), nullable=False),
        sa.Column("fec_filing_id", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_contributions_donor_id", "contributions", ["donor_id"])
    op.create_index(
        "ix_contributions_representative_id", "contributions", ["representative_id"]
    )
    op.create_index("ix_contributions_election_cycle", "contributions", ["election_cycle"])
    op.create_index("ix_contributions_contributed_on", "contributions", ["contributed_on"])

    op.create_table(
        "donor_rep_relationships",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("donor_id", sa.String(26), sa.ForeignKey("donors.id"), nullable=False),
        sa.Column(
            "representative_id",
            sa.String(26),
            sa.ForeignKey("representatives.id"),
            nullable=False,
        ),
        sa.Column("total_amount_cents", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("first_donation_date", sa.Date, nullable=True),
        sa.Column("latest_donation_date", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_relationships_donor_id", "donor_rep_relationships", ["donor_id"]
    )
    op.create_index(
        "ix_relationships_representative_id",
        "donor_rep_relationships",
        ["representative_id"],
    )
    op.create_unique_constraint(
        "uq_relationships_donor_rep",
        "donor_rep_relationships",
        ["donor_id", "representative_id"],
    )

    op.create_table(
        "bills",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("industries", sa.Text, nullable=False, server_default="[]"),
        sa.Column("nlp_confidence", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("congress", sa.Integer, nullable=True),
        sa.Column("propublica_id", sa.String(50), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "votes",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("bill_id", sa.String(26), sa.ForeignKey("bills.id"), nullable=False),
        sa.Column(
            "representative_id",
            sa.String(26),
            sa.ForeignKey("representatives.id"),
            nullable=False,
        ),
        sa.Column("position", sa.String(15), nullable=False),
        sa.Column("voted_at", sa.DateTime, nullable=False),
        sa.Column("vote_type", sa.String(15), nullable=False, server_default="floor"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_votes_bill_id", "votes", ["bill_id"])
    op.create_index("ix_votes_representative_id", "votes", ["representative_id"])
    op.create_index("ix_votes_voted_at", "votes", ["voted_at"])


def downgrade() -> None:
    op.drop_table("votes")
    op.drop_table("bills")
    op.drop_table("donor_rep_relationships")
    op.drop_table("contributions")
    op.drop_table("donors")
    op.drop_table("representatives")
