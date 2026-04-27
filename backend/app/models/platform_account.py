"""Credential/OAuth record per POD platform per user."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, func
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

    # Misc
    extra: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User")
