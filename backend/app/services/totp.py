"""TOTP (RFC 6238) implementation for the 2FA admin login flow.

We avoid pulling pyotp because (a) it adds a dependency for a few dozen
lines of code and (b) we want to keep the secret encryption flow inline
with our existing Fernet wrapper. The implementation here is a strict
RFC 6238 reading: 30s step, SHA1, 6 digits.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

DIGITS = 6
STEP_SECONDS = 30
ALGORITHM = "SHA1"


def generate_secret() -> str:
    """Return a fresh base32-encoded 160-bit secret."""
    raw = secrets.token_bytes(20)
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def _hotp(secret_b32: str, counter: int) -> str:
    padded = secret_b32 + "=" * (-len(secret_b32) % 8)
    key = base64.b32decode(padded.upper())
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**DIGITS)).zfill(DIGITS)


def now_code(secret_b32: str, *, at: float | None = None) -> str:
    counter = int((at if at is not None else time.time()) // STEP_SECONDS)
    return _hotp(secret_b32, counter)


def verify(
    secret_b32: str,
    submitted: str,
    *,
    drift_steps: int = 1,
    at: float | None = None,
) -> bool:
    """Verify ``submitted`` against ``secret_b32`` allowing ±drift_steps slips.

    A drift of 1 means we accept the previous and next 30s window —
    handy when the user's clock is slightly off.
    """
    if not submitted or not secret_b32:
        return False
    submitted = submitted.strip().replace(" ", "").replace("-", "")
    if not submitted.isdigit() or len(submitted) != DIGITS:
        return False
    base_counter = int((at if at is not None else time.time()) // STEP_SECONDS)
    for delta in range(-drift_steps, drift_steps + 1):
        if hmac.compare_digest(_hotp(secret_b32, base_counter + delta), submitted):
            return True
    return False


def provisioning_uri(*, secret_b32: str, label: str, issuer: str = "POD Bot") -> str:
    """Build an otpauth:// URI users can scan into Google Authenticator / 1Password."""
    label_q = quote(f"{issuer}:{label}", safe="")
    issuer_q = quote(issuer, safe="")
    secret_q = quote(secret_b32, safe="")
    return (
        f"otpauth://totp/{label_q}?secret={secret_q}&issuer={issuer_q}"
        f"&algorithm={ALGORITHM}&digits={DIGITS}&period={STEP_SECONDS}"
    )


def random_recovery_codes(n: int = 8) -> list[str]:
    """One-time recovery codes shown when 2FA is enrolled."""
    return ["-".join(secrets.token_hex(2) for _ in range(3)) for _ in range(n)]


def is_strong_secret(secret_b32: str) -> bool:
    """Sanity check used in tests + admin reset flow."""
    if not secret_b32 or len(secret_b32) < 16:
        return False
    try:
        padded = secret_b32 + "=" * (-len(secret_b32) % 8)
        decoded = base64.b32decode(padded.upper())
    except Exception:  # noqa: BLE001
        return False
    return len(decoded) >= 10 and decoded != bytes(len(decoded))
