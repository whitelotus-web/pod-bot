"""Symmetric encryption helper for storing user-provided API keys.

Fernet (AES-128-CBC + HMAC) keyed off the app SECRET_KEY. We derive a
deterministic 32-byte key via SHA-256 so rotating SECRET_KEY invalidates
all stored secrets — that is intentional.
"""
from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


@lru_cache
def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Không giải mã được API key (SECRET_KEY có thể đã đổi).") from exc


def mask(plain: str, keep: int = 4) -> str:
    if not plain:
        return ""
    if len(plain) <= keep * 2:
        return "•" * len(plain)
    return f"{plain[:keep]}{'•' * 6}{plain[-keep:]}"
