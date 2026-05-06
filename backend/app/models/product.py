from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    design_id: Mapped[int] = mapped_column(
        ForeignKey("designs.id", ondelete="CASCADE"), index=True
    )
    platform_account_id: Mapped[int] = mapped_column(
        ForeignKey("platform_accounts.id", ondelete="CASCADE"), index=True
    )

    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    product_type: Mapped[str] = mapped_column(String(64), default="tshirt_unisex")
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    price_usd: Mapped[float] = mapped_column(default=19.99)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    # ^ draft | published | pending_retry | failed | failed_terminal
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Retry queue bookkeeping (Wave 5)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_retry_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Per-product wholesale cost (Wave 5) — used by /pnl P&L aggregation.
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # Lifecycle metrics (synced from platform webhooks)
    views_count: Mapped[int] = mapped_column(Integer, default=0)
    clicks_count: Mapped[int] = mapped_column(Integer, default=0)
    orders_count: Mapped[int] = mapped_column(Integer, default=0)
    revenue_usd: Mapped[float] = mapped_column(Float, default=0.0)
    ctr: Mapped[float] = mapped_column(Float, default=0.0)
    last_metrics_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lifecycle_stage: Mapped[str] = mapped_column(String(32), default="active")
    delisted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    design = relationship("Design")
    platform_account = relationship("PlatformAccount")
