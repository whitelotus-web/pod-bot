from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Mockup(Base):
    __tablename__ = "mockups"

    id: Mapped[int] = mapped_column(primary_key=True)
    design_id: Mapped[int] = mapped_column(
        ForeignKey("designs.id", ondelete="CASCADE"), index=True
    )
    product_type: Mapped[str] = mapped_column(String(64))  # tshirt, hoodie...
    template: Mapped[str] = mapped_column(String(128), default="tshirt_white")
    file_path: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    design = relationship("Design")
