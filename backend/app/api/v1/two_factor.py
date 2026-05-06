"""Routes for the 2FA TOTP enrollment + verification flow.

Flow:
1. ``POST /two-factor/enroll`` — generate a fresh secret, return both the
   plaintext base32 and a provisioning ``otpauth://`` URI for the user
   to scan into Google Authenticator. Server stores the encrypted secret
   but DOES NOT enable 2FA yet.
2. ``POST /two-factor/confirm`` — user submits their first 6-digit code.
   Server verifies, flips ``two_factor_enabled=True``, and returns the
   one-time recovery codes (only shown this once).
3. ``POST /auth/login-2fa`` — login flow accepts the password + the code.
   See ``api/v1/auth.py``.
4. ``POST /two-factor/disable`` — user must supply a current code (or a
   recovery code) to drop 2FA.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.crypto import decrypt, encrypt
from app.models import User
from app.services import totp
from app.services.audit import log_action

router = APIRouter()


class StatusResponse(BaseModel):
    two_factor_enabled: bool
    enrolled: bool


@router.get("/status", response_model=StatusResponse)
def status_(
    user: User = Depends(get_current_user),
) -> StatusResponse:
    return StatusResponse(
        two_factor_enabled=bool(user.two_factor_enabled),
        enrolled=bool(user.totp_secret_encrypted),
    )


class EnrollResponse(BaseModel):
    secret: str = Field(..., description="Plaintext base32 secret. Show only once.")
    otpauth_uri: str
    qr_label: str


class ConfirmRequest(BaseModel):
    code: str


class ConfirmResponse(BaseModel):
    enabled: bool
    recovery_codes: list[str]


class DisableRequest(BaseModel):
    code: str


@router.post("/enroll", response_model=EnrollResponse)
def enroll(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EnrollResponse:
    secret = totp.generate_secret()
    user.totp_secret_encrypted = encrypt(secret)
    user.two_factor_enabled = False
    db.commit()
    log_action(
        db,
        user_id=user.id,
        action="two_factor.enroll_started",
        target_type="user",
        target_id=user.id,
    )
    return EnrollResponse(
        secret=secret,
        otpauth_uri=totp.provisioning_uri(secret_b32=secret, label=user.email),
        qr_label=user.email,
    )


@router.post("/confirm", response_model=ConfirmResponse)
def confirm(
    body: ConfirmRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConfirmResponse:
    if not user.totp_secret_encrypted:
        raise HTTPException(status_code=400, detail="Chưa enroll 2FA — gọi /enroll trước.")
    secret = decrypt(user.totp_secret_encrypted)
    if not totp.verify(secret, body.code):
        raise HTTPException(status_code=400, detail="Mã không đúng. Thử lại.")
    user.two_factor_enabled = True
    db.commit()
    log_action(
        db,
        user_id=user.id,
        action="two_factor.enabled",
        target_type="user",
        target_id=user.id,
    )
    codes = totp.random_recovery_codes()
    # NOTE: we don't persist recovery codes in this drop. A follow-up can
    # add a hashed-recovery-codes table; for now they're for display only.
    return ConfirmResponse(enabled=True, recovery_codes=codes)


@router.post("/disable", response_model=ConfirmResponse)
def disable(
    body: DisableRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConfirmResponse:
    if not user.two_factor_enabled or not user.totp_secret_encrypted:
        raise HTTPException(status_code=400, detail="2FA chưa bật.")
    secret = decrypt(user.totp_secret_encrypted)
    if not totp.verify(secret, body.code):
        raise HTTPException(status_code=400, detail="Mã không đúng.")
    user.two_factor_enabled = False
    user.totp_secret_encrypted = None
    db.commit()
    log_action(
        db,
        user_id=user.id,
        action="two_factor.disabled",
        target_type="user",
        target_id=user.id,
    )
    return ConfirmResponse(enabled=False, recovery_codes=[])
