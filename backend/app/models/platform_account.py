"""Credential/OAuth record per POD platform per user."""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class PlatformAccount(Base):
    __tablename__ = "platform_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # First-class API-backed platforms: "printify" | "printful" | "etsy"
    platform: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(255), default="")

    # For API-key platforms
    api_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    shop_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # For OAuth platforms
    access_token: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Multi-account fingerprint isolation (one shop per IP/UA pattern)
    proxy_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Warm-up: cap publishes/day; override age (for migrated existing accounts)
    account_age_days_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daily_publish_cap_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    today_publish_count: Mapped[int] = mapped_column(Integer, default=0)
    today_publish_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Health monitor
    health_status: Mapped[str] = mapped_column(String(32), default="healthy")  # healthy|warn|paused|banned
    health_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Misc
    extra: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User")
