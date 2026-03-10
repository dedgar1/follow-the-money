"""Add raw ingestion tables: raw_filings, raw_votes

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-09

These tables hold verbatim API payloads and are IMMUTABLE after insert.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "raw_filings",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="fec_api"),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("committee_id", sa.String(50), nullable=False, server_default=""),
        sa.Column("contributor_name", sa.String(500), nullable=False, server_default=""),
        sa.Column("contributor_employer", sa.String(500), nullable=False, server_default=""),
        sa.Column("contributor_occupation", sa.String(500), nullable=False, server_default=""),
        sa.Column("contributor_state", sa.String(2), nullable=False, server_default=""),
        sa.Column("amount_cents", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("contribution_date", sa.String(10), nullable=False, server_default=""),
        sa.Column("election_cycle", sa.Integer, nullable=False, server_default="0"),
        sa.Column("payload", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("fetched_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("is_processed", sa.Boolean, nullable=False, server_default="false"),
    )
    op.create_unique_constraint(
        "uq_raw_filings_source_source_id", "raw_filings", ["source", "source_id"]
    )
    op.create_index("ix_raw_filings_election_cycle", "raw_filings", ["election_cycle"])
    op.create_index("ix_raw_filings_committee_id", "raw_filings", ["committee_id"])
    op.create_index("ix_raw_filings_is_processed", "raw_filings", ["is_processed"])

    op.create_table(
        "raw_votes",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="congress_api"),
        sa.Column("source_id", sa.String(300), nullable=False),
        sa.Column("congress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("session", sa.Integer, nullable=False, server_default="1"),
        sa.Column("chamber", sa.String(10), nullable=False, server_default=""),
        sa.Column("roll_call", sa.Integer, nullable=False, server_default="0"),
        sa.Column("bill_id", sa.String(50), nullable=False, server_default=""),
        sa.Column("bill_title", sa.Text, nullable=False, server_default=""),
        sa.Column("member_bioguide_id", sa.String(20), nullable=False, server_default=""),
        sa.Column("member_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("position", sa.String(20), nullable=False, server_default=""),
        sa.Column("voted_at", sa.String(10), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("fetched_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("is_processed", sa.Boolean, nullable=False, server_default="false"),
    )
    op.create_unique_constraint(
        "uq_raw_votes_source_member", "raw_votes", ["source_id", "member_bioguide_id"]
    )
    op.create_index("ix_raw_votes_congress", "raw_votes", ["congress"])
    op.create_index("ix_raw_votes_member_bioguide_id", "raw_votes", ["member_bioguide_id"])
    op.create_index("ix_raw_votes_is_processed", "raw_votes", ["is_processed"])


def downgrade() -> None:
    op.drop_table("raw_votes")
    op.drop_table("raw_filings")
