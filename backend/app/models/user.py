from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    # 2FA TOTP — secret stored Fernet-encrypted; flag toggles enforcement on login.
    totp_secret_encrypted: Mapped[str | None] = mapped_column(String(255), nullable=True)
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    locale: Mapped[str] = mapped_column(String(8), default="vi")  # ui language: vi | en
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
