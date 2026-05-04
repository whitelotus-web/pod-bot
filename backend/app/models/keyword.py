from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True, nullable=True
    )

    term: Mapped[str] = mapped_column(String(255), index=True)
    source: Mapped[str] = mapped_column(String(64))  # google_trends | etsy | amazon | ...
    score: Mapped[float] = mapped_column(Float, default=0)  # chuẩn hoá 0-100
    rank: Mapped[int] = mapped_column(Integer, default=0)
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Momentum analytics
    momentum_score: Mapped[float] = mapped_column(Float, default=0)
    rsi_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma_7: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma_30: Mapped[float | None] = mapped_column(Float, nullable=True)
    breakout_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)

    campaign = relationship("Campaign")


class KeywordVolumeHistory(Base):
    """Time-series volume samples used to compute SMA/RSI."""

    __tablename__ = "keyword_volume_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword_id: Mapped[int] = mapped_column(
        ForeignKey("keywords.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    volume: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32))
