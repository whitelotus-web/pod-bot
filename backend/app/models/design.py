from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Design(Base):
    __tablename__ = "designs"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True, nullable=True
    )
    keyword_id: Mapped[int | None] = mapped_column(
        ForeignKey("keywords.id", ondelete="SET NULL"), index=True, nullable=True
    )

    title: Mapped[str] = mapped_column(String(255))
    prompt: Mapped[str] = mapped_column(Text)
    engine: Mapped[str] = mapped_column(String(32))  # gemini | openai | replicate
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)

    file_path: Mapped[str] = mapped_column(String(512))  # relative to MEDIA_ROOT
    bg_removed_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="ready")  # ready|approved|rejected
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Quality gate output
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    campaign = relationship("Campaign")
    keyword = relationship("Keyword")
