"""Wave 4: AI upscaler — add print-ready columns to designs + campaign config.

Revision ID: 0005_upscale_columns
Revises: 0004_quality_risk_lifecycle
Create Date: 2026-04-27
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_upscale_columns"
down_revision = "0004_quality_risk_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("designs", sa.Column("upscaled_path", sa.String(length=512), nullable=True))
    op.add_column("designs", sa.Column("upscale_backend", sa.String(length=32), nullable=True))
    op.add_column("designs", sa.Column("print_width", sa.Integer(), nullable=True))
    op.add_column("designs", sa.Column("print_height", sa.Integer(), nullable=True))

    op.add_column(
        "campaigns",
        sa.Column("upscale_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "campaigns",
        sa.Column(
            "upscale_min_long_edge",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("4500"),
        ),
    )


def downgrade() -> None:
    op.drop_column("campaigns", "upscale_min_long_edge")
    op.drop_column("campaigns", "upscale_enabled")
    op.drop_column("designs", "print_height")
    op.drop_column("designs", "print_width")
    op.drop_column("designs", "upscale_backend")
    op.drop_column("designs", "upscaled_path")
