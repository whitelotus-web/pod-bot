from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class RunLog(Base):
    """Mỗi lần chạy pipeline được lưu lại để user theo dõi."""

    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True, nullable=True
    )
    stage: Mapped[str] = mapped_column(String(64))  # keywords|design|mockup|publish|pipeline
    status: Mapped[str] = mapped_column(String(32), default="running")  # running|success|failed
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    campaign = relationship("Campaign")
