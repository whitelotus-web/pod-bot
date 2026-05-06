"""Common FastAPI dependencies."""
from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import decode_token
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    email = decode_token(token)
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ")
    user = db.query(User).filter_by(email=email).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không hợp lệ")
    return user


def get_user_from_token(token: str, db: Session) -> User | None:
    """Best-effort token → user lookup for the rate-limit middleware.

    Returns ``None`` instead of raising so unauthenticated requests still
    get processed (they fall back to IP-keyed limiting).
    """
    try:
        email = decode_token(token)
    except Exception:  # noqa: BLE001
        return None
    if not email:
        return None
    return db.query(User).filter_by(email=email).first()
