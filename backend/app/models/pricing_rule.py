"""User-defined dynamic pricing rule."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class PricingRule(Base):
    __tablename__ = "pricing_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    trigger: Mapped[str] = mapped_column(String(32))  # high_momentum|weekend_flash|low_ctr_discount
    delta_usd: Mapped[float] = mapped_column(Float, default=0.0)
    delta_percent: Mapped[float] = mapped_column(Float, default=0.0)
    min_price_usd: Mapped[float] = mapped_column(Float, default=0.0)
    max_price_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
