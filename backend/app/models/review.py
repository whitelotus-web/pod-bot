from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class ProductReview(Base):
    """Review pulled from Etsy/Printify for a published product.

    One row per platform review. We dedupe on
    ``(product_id, external_review_id)`` to avoid duplicates when the
    review-poll beat task runs multiple times.
    """

    __tablename__ = "product_reviews"
    __table_args__ = (
        UniqueConstraint("product_id", "external_review_id", name="uq_review_product_extid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    external_review_id: Mapped[str] = mapped_column(String(128))
    rating: Mapped[float] = mapped_column(Float)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    alert_sent: Mapped[int] = mapped_column(Integer, default=0)
    # ^ 0 = not yet, 1 = telegram alert pushed (only for low ratings)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    product = relationship("Product")
