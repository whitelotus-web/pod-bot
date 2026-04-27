"""Campaign — cấu hình cho pipeline auto."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String(255))
    niche: Mapped[str] = mapped_column(String(255), default="")  # ví dụ "cat lovers"
    style_prompt: Mapped[str] = mapped_column(String(2048), default="")  # style design

    # --- Keyword sources (danh sách trong JSON) ---
    keyword_sources: Mapped[list] = mapped_column(JSON, default=list)  # ["google_trends","etsy",...]

    # --- AI engine ---
    ai_engine: Mapped[str] = mapped_column(String(32), default="gemini")  # gemini|openai|replicate
    ai_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    designs_per_keyword: Mapped[int] = mapped_column(Integer, default=2)

    # --- Mockup + Product ---
    product_types: Mapped[list] = mapped_column(JSON, default=list)  # ["tshirt","hoodie"]
    base_price_usd: Mapped[float] = mapped_column(default=19.99)

    # --- Auto-publish ---
    auto_mode: Mapped[str] = mapped_column(String(16), default="semi")  # semi | full
    target_platforms: Mapped[list] = mapped_column(JSON, default=list)  # ["printify","etsy"]

    # --- Schedule ---
    schedule_cron: Mapped[str | None] = mapped_column(String(64), nullable=True)  # "0 3 * * *"
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User")
