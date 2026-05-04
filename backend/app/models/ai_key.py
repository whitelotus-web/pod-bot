"""User-managed AI engine API keys (encrypted at rest).

Roles separate which AI key handles which job:
  - image_generation : creates the design PNG  (Gemini Flash Image / DALL-E / SDXL)
  - seo_writer       : writes title/tags/description (Gemini text / GPT-4o-mini)
  - keyword_expansion: expands the seed niche into long-tail terms

The pipeline picks the active (role, engine, priority=asc) key first and
auto fails over to higher-priority numbers if a quota / 429 is hit.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

ROLES = ("image_generation", "seo_writer", "keyword_expansion")


class AIKey(Base):
    __tablename__ = "ai_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    role: Mapped[str] = mapped_column(String(32), default="image_generation", index=True)

    # gemini | openai | replicate (matches AIDesignEngine.name)
    engine: Mapped[str] = mapped_column(String(32), index=True)
    label: Mapped[str] = mapped_column(String(255), default="")

    encrypted_key: Mapped[str] = mapped_column(String(1024))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Lower number = tried first. Same priority rotates round-robin.
    priority: Mapped[int] = mapped_column(Integer, default=1)

    # Counter — bumped when provider returns 429 / quota exceeded.
    quota_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User")
