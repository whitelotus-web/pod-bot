"""Full optimization (Wave 6 + 7 + 8): hardening, P&L accuracy, 2FA, A/B tests.

Revision ID: 0007_full_optimization
Revises: 0006_optimization_wave5
Create Date: 2026-04-27 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007_full_optimization"
down_revision = "0006_optimization_wave5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Audit log -----------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.Integer, nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("payload", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # --- Product reviews -----------------------------------------------------
    op.create_table(
        "product_reviews",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "product_id",
            sa.Integer,
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_review_id", sa.String(128), nullable=False),
        sa.Column("rating", sa.Float, nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("reviewer_name", sa.String(128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("alert_sent", sa.Integer, server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "product_id", "external_review_id", name="uq_review_product_extid"
        ),
    )
    op.create_index("ix_product_reviews_product_id", "product_reviews", ["product_id"])

    # --- 2FA + locale on users -----------------------------------------------
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("totp_secret_encrypted", sa.String(255), nullable=True))
        batch.add_column(
            sa.Column(
                "two_factor_enabled",
                sa.Boolean,
                server_default=sa.false(),
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "locale", sa.String(8), server_default="vi", nullable=False
            )
        )

    # --- A/B variant + fees + refunds on campaigns + products ---------------
    with op.batch_alter_table("campaigns") as batch:
        batch.add_column(sa.Column("ab_test_group", sa.String(64), nullable=True))
        batch.add_column(sa.Column("ab_variant_label", sa.String(16), nullable=True))
        batch.add_column(
            sa.Column(
                "ab_test_winner",
                sa.Boolean,
                server_default=sa.false(),
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column("ab_test_concluded_at", sa.DateTime(timezone=True), nullable=True)
        )
    op.create_index("ix_campaigns_ab_test_group", "campaigns", ["ab_test_group"])

    with op.batch_alter_table("products") as batch:
        batch.add_column(
            sa.Column(
                "refunds_usd",
                sa.Float,
                server_default="0",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "refunds_count",
                sa.Integer,
                server_default="0",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "platform_fees_usd",
                sa.Float,
                server_default="0",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "ads_spend_usd",
                sa.Float,
                server_default="0",
                nullable=False,
            )
        )
        batch.add_column(sa.Column("ab_test_group", sa.String(64), nullable=True))
        batch.add_column(sa.Column("ab_variant_label", sa.String(16), nullable=True))
    op.create_index("ix_products_ab_test_group", "products", ["ab_test_group"])


def downgrade() -> None:
    op.drop_index("ix_products_ab_test_group", table_name="products")
    with op.batch_alter_table("products") as batch:
        batch.drop_column("ab_variant_label")
        batch.drop_column("ab_test_group")
        batch.drop_column("ads_spend_usd")
        batch.drop_column("platform_fees_usd")
        batch.drop_column("refunds_count")
        batch.drop_column("refunds_usd")

    op.drop_index("ix_campaigns_ab_test_group", table_name="campaigns")
    with op.batch_alter_table("campaigns") as batch:
        batch.drop_column("ab_test_concluded_at")
        batch.drop_column("ab_test_winner")
        batch.drop_column("ab_variant_label")
        batch.drop_column("ab_test_group")

    with op.batch_alter_table("users") as batch:
        batch.drop_column("locale")
        batch.drop_column("two_factor_enabled")
        batch.drop_column("totp_secret_encrypted")

    op.drop_index("ix_product_reviews_product_id", table_name="product_reviews")
    op.drop_table("product_reviews")

    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")
