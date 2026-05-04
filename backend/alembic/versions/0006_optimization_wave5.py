"""Optimization Wave 5: buyer-intent + retry-queue + P&L cost tracking.

Revision ID: 0006_optimization_wave5
Revises: 0005_upscale_columns
Create Date: 2025-04-27 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_optimization_wave5"
down_revision = "0005_upscale_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Buyer-intent on keywords ------------------------------------------
    with op.batch_alter_table("keywords") as batch:
        batch.add_column(
            sa.Column("intent", sa.String(32), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "intent_score",
                sa.Float,
                nullable=False,
                server_default="0",
            )
        )

    # --- Retry-queue on products -------------------------------------------
    with op.batch_alter_table("products") as batch:
        batch.add_column(
            sa.Column(
                "retry_count",
                sa.Integer,
                nullable=False,
                server_default="0",
            )
        )
        batch.add_column(
            sa.Column(
                "next_retry_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column("last_retry_error", sa.Text, nullable=True)
        )
        batch.add_column(
            sa.Column(
                "cost_usd",
                sa.Float,
                nullable=False,
                server_default="0",
            )
        )
    op.create_index(
        "ix_products_pending_retry",
        "products",
        ["status", "next_retry_at"],
        unique=False,
    )

    # --- Cost tracking on designs ------------------------------------------
    with op.batch_alter_table("designs") as batch:
        batch.add_column(
            sa.Column(
                "cost_usd",
                sa.Float,
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    op.drop_index("ix_products_pending_retry", table_name="products")
    with op.batch_alter_table("designs") as batch:
        batch.drop_column("cost_usd")
    with op.batch_alter_table("products") as batch:
        batch.drop_column("cost_usd")
        batch.drop_column("last_retry_error")
        batch.drop_column("next_retry_at")
        batch.drop_column("retry_count")
    with op.batch_alter_table("keywords") as batch:
        batch.drop_column("intent_score")
        batch.drop_column("intent")
