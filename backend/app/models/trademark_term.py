"""User-managed trademark blacklist (extends builtin list)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class TrademarkTerm(Base):
    __tablename__ = "trademark_terms"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    term: Mapped[str] = mapped_column(String(255), index=True)
    source: Mapped[str] = mapped_column(String(32), default="user")  # user|auto_dmca|builtin_extra
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
