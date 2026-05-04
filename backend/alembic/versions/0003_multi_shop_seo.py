"""Add target_account_ids to campaigns + bg_removed_path to designs + seo fields to products.

Revision ID: 0003_multi_shop_seo
Revises: 0002_ai_keys
Create Date: 2026-04-27 03:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_multi_shop_seo"
down_revision: str | None = "0002_ai_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("target_account_ids", sa.JSON(), server_default=sa.text("'[]'::json")),
    )
    op.add_column(
        "campaigns",
        sa.Column("seo_auto", sa.Boolean(), server_default=sa.text("true")),
    )
    op.add_column(
        "designs",
        sa.Column("bg_removed_path", sa.String(512), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("product_type", sa.String(64), server_default="tshirt_unisex"),
    )
    # AI role system on ai_keys
    op.add_column(
        "ai_keys",
        sa.Column("role", sa.String(32), server_default="image_generation"),
    )
    op.add_column(
        "ai_keys",
        sa.Column("priority", sa.Integer(), server_default="1"),
    )
    op.add_column(
        "ai_keys",
        sa.Column("quota_failures", sa.Integer(), server_default="0"),
    )
    op.add_column(
        "ai_keys",
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ai_keys_role", "ai_keys", ["role"])


def downgrade() -> None:
    op.drop_index("ix_ai_keys_role", table_name="ai_keys")
    op.drop_column("ai_keys", "last_used_at")
    op.drop_column("ai_keys", "quota_failures")
    op.drop_column("ai_keys", "priority")
    op.drop_column("ai_keys", "role")
    op.drop_column("products", "product_type")
    op.drop_column("designs", "bg_removed_path")
    op.drop_column("campaigns", "seo_auto")
    op.drop_column("campaigns", "target_account_ids")
