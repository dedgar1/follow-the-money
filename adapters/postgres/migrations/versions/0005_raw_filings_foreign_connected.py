"""Add foreign_connected column to raw_filings.

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "raw_filings",
        sa.Column("foreign_connected", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("raw_filings", "foreign_connected")
