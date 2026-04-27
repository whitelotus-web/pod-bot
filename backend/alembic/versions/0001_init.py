"""Initial schema.

Revision ID: 0001_init
Revises:
Create Date: 2025-04-27 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_init"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("is_superuser", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "platform_accounts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("platform", sa.String(64), index=True, nullable=False),
        sa.Column("label", sa.String(255), server_default=""),
        sa.Column("api_key", sa.String(512)),
        sa.Column("shop_id", sa.String(128)),
        sa.Column("access_token", sa.String(2048)),
        sa.Column("refresh_token", sa.String(2048)),
        sa.Column("token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("extra", sa.JSON),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("niche", sa.String(255), server_default=""),
        sa.Column("style_prompt", sa.String(2048), server_default=""),
        sa.Column("keyword_sources", sa.JSON),
        sa.Column("ai_engine", sa.String(32), server_default="gemini"),
        sa.Column("ai_model", sa.String(64)),
        sa.Column("designs_per_keyword", sa.Integer, server_default="2"),
        sa.Column("product_types", sa.JSON),
        sa.Column("base_price_usd", sa.Float, server_default="19.99"),
        sa.Column("auto_mode", sa.String(16), server_default="semi"),
        sa.Column("target_platforms", sa.JSON),
        sa.Column("schedule_cron", sa.String(64)),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "keywords",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("campaign_id", sa.Integer, sa.ForeignKey("campaigns.id", ondelete="CASCADE"), index=True),
        sa.Column("term", sa.String(255), index=True, nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("score", sa.Float, server_default="0"),
        sa.Column("rank", sa.Integer, server_default="0"),
        sa.Column("raw", sa.JSON),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "designs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("campaign_id", sa.Integer, sa.ForeignKey("campaigns.id", ondelete="CASCADE"), index=True),
        sa.Column("keyword_id", sa.Integer, sa.ForeignKey("keywords.id", ondelete="SET NULL"), index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("engine", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64)),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("thumbnail_path", sa.String(512)),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        sa.Column("status", sa.String(32), server_default="ready"),
        sa.Column("meta", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "mockups",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("design_id", sa.Integer, sa.ForeignKey("designs.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("product_type", sa.String(64), nullable=False),
        sa.Column("template", sa.String(128), server_default="tshirt_white"),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("source", sa.String(32), server_default="pillow"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("design_id", sa.Integer, sa.ForeignKey("designs.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("platform_account_id", sa.Integer, sa.ForeignKey("platform_accounts.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("external_id", sa.String(255)),
        sa.Column("url", sa.String(1024)),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("tags", sa.JSON),
        sa.Column("price_usd", sa.Float, server_default="19.99"),
        sa.Column("status", sa.String(32), server_default="draft"),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "run_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("campaign_id", sa.Integer, sa.ForeignKey("campaigns.id", ondelete="CASCADE"), index=True),
        sa.Column("stage", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="running"),
        sa.Column("message", sa.Text),
        sa.Column("data", sa.JSON),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    for t in (
        "run_logs",
        "products",
        "mockups",
        "designs",
        "keywords",
        "campaigns",
        "platform_accounts",
        "users",
    ):
        op.drop_table(t)
