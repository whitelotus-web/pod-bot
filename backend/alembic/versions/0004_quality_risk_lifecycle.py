"""Quality gates, trademark blacklist, account risk isolation, lifecycle metrics.

Revision ID: 0004_quality_risk_lifecycle
Revises: 0003_multi_shop_seo
Create Date: 2026-04-27 12:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_quality_risk_lifecycle"
down_revision: str | None = "0003_multi_shop_seo"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── designs: quality gate output ──
    op.add_column("designs", sa.Column("quality_score", sa.Float(), nullable=True))
    op.add_column("designs", sa.Column("quality_report", sa.JSON(), nullable=True))
    op.add_column("designs", sa.Column("template_id", sa.String(64), nullable=True))
    op.add_column("designs", sa.Column("rejection_reason", sa.Text(), nullable=True))

    # ── platform_accounts: warm-up + fingerprint isolation + health ──
    op.add_column("platform_accounts", sa.Column("proxy_url", sa.String(512), nullable=True))
    op.add_column("platform_accounts", sa.Column("user_agent", sa.String(512), nullable=True))
    op.add_column("platform_accounts", sa.Column("account_age_days_override", sa.Integer(), nullable=True))
    op.add_column("platform_accounts", sa.Column("daily_publish_cap_override", sa.Integer(), nullable=True))
    op.add_column("platform_accounts", sa.Column("today_publish_count", sa.Integer(), server_default="0"))
    op.add_column("platform_accounts", sa.Column("today_publish_date", sa.Date(), nullable=True))
    op.add_column("platform_accounts", sa.Column("last_publish_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("platform_accounts", sa.Column("health_status", sa.String(32), server_default="healthy"))
    op.add_column("platform_accounts", sa.Column("health_note", sa.Text(), nullable=True))
    op.add_column("platform_accounts", sa.Column("paused_until", sa.DateTime(timezone=True), nullable=True))

    # ── campaigns: vision QA + trademark check toggles, prompt template family ──
    op.add_column(
        "campaigns",
        sa.Column("quality_gates_enabled", sa.Boolean(), server_default=sa.text("true")),
    )
    op.add_column(
        "campaigns",
        sa.Column("vision_qa_enabled", sa.Boolean(), server_default=sa.text("false")),
    )
    op.add_column(
        "campaigns",
        sa.Column("trademark_check_enabled", sa.Boolean(), server_default=sa.text("true")),
    )
    op.add_column(
        "campaigns",
        sa.Column("uspto_check_enabled", sa.Boolean(), server_default=sa.text("false")),
    )
    op.add_column(
        "campaigns",
        sa.Column("prompt_template_ids", sa.JSON(), server_default=sa.text("'[]'::json")),
    )

    # ── products: lifecycle metrics ──
    op.add_column("products", sa.Column("views_count", sa.Integer(), server_default="0"))
    op.add_column("products", sa.Column("clicks_count", sa.Integer(), server_default="0"))
    op.add_column("products", sa.Column("orders_count", sa.Integer(), server_default="0"))
    op.add_column("products", sa.Column("revenue_usd", sa.Float(), server_default="0"))
    op.add_column("products", sa.Column("ctr", sa.Float(), server_default="0"))
    op.add_column("products", sa.Column("last_metrics_sync_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("products", sa.Column("lifecycle_stage", sa.String(32), server_default="active"))
    op.add_column("products", sa.Column("delisted_at", sa.DateTime(timezone=True), nullable=True))

    # ── keywords: momentum tracking ──
    op.add_column("keywords", sa.Column("momentum_score", sa.Float(), server_default="0"))
    op.add_column("keywords", sa.Column("rsi_14", sa.Float(), nullable=True))
    op.add_column("keywords", sa.Column("sma_7", sa.Float(), nullable=True))
    op.add_column("keywords", sa.Column("sma_30", sa.Float(), nullable=True))
    op.add_column("keywords", sa.Column("breakout_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("keywords", sa.Column("rejected_reason", sa.String(512), nullable=True))

    # ── new: trademark_terms (user-managed blacklist) ──
    op.create_table(
        "trademark_terms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("term", sa.String(255), index=True),
        sa.Column("source", sa.String(32), server_default="user"),  # user | auto_dmca | builtin_extra
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── new: keyword_volume_history (for SMA/RSI computation) ──
    op.create_table(
        "keyword_volume_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("keyword_id", sa.Integer(), sa.ForeignKey("keywords.id", ondelete="CASCADE"), index=True),
        sa.Column("date", sa.Date(), index=True),
        sa.Column("volume", sa.Float()),
        sa.Column("source", sa.String(32)),
    )

    # ── new: notifications (for Telegram + dashboard alerts) ──
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("kind", sa.String(64)),  # quota_exhausted | trademark_hit | sale | account_paused | design_review
        sa.Column("severity", sa.String(16), server_default="info"),  # info|warn|critical
        sa.Column("title", sa.String(255)),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )

    # ── new: pricing_rules ──
    op.create_table(
        "pricing_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("name", sa.String(128)),
        sa.Column("trigger", sa.String(32)),  # high_momentum | weekend_flash | low_ctr_discount
        sa.Column("delta_usd", sa.Float(), server_default="0"),
        sa.Column("delta_percent", sa.Float(), server_default="0"),
        sa.Column("min_price_usd", sa.Float(), server_default="0"),
        sa.Column("max_price_usd", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("pricing_rules")
    op.drop_table("notifications")
    op.drop_table("keyword_volume_history")
    op.drop_table("trademark_terms")

    op.drop_column("keywords", "rejected_reason")
    op.drop_column("keywords", "breakout_at")
    op.drop_column("keywords", "sma_30")
    op.drop_column("keywords", "sma_7")
    op.drop_column("keywords", "rsi_14")
    op.drop_column("keywords", "momentum_score")

    op.drop_column("products", "delisted_at")
    op.drop_column("products", "lifecycle_stage")
    op.drop_column("products", "last_metrics_sync_at")
    op.drop_column("products", "ctr")
    op.drop_column("products", "revenue_usd")
    op.drop_column("products", "orders_count")
    op.drop_column("products", "clicks_count")
    op.drop_column("products", "views_count")

    op.drop_column("campaigns", "prompt_template_ids")
    op.drop_column("campaigns", "uspto_check_enabled")
    op.drop_column("campaigns", "trademark_check_enabled")
    op.drop_column("campaigns", "vision_qa_enabled")
    op.drop_column("campaigns", "quality_gates_enabled")

    op.drop_column("platform_accounts", "paused_until")
    op.drop_column("platform_accounts", "health_note")
    op.drop_column("platform_accounts", "health_status")
    op.drop_column("platform_accounts", "last_publish_at")
    op.drop_column("platform_accounts", "today_publish_date")
    op.drop_column("platform_accounts", "today_publish_count")
    op.drop_column("platform_accounts", "daily_publish_cap_override")
    op.drop_column("platform_accounts", "account_age_days_override")
    op.drop_column("platform_accounts", "user_agent")
    op.drop_column("platform_accounts", "proxy_url")

    op.drop_column("designs", "rejection_reason")
    op.drop_column("designs", "template_id")
    op.drop_column("designs", "quality_report")
    op.drop_column("designs", "quality_score")
