from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models import PlatformAccount, User
from app.schemas.platform_account import (
    PlatformAccountCreate,
    PlatformAccountRead,
    PlatformAccountUpdate,
)
from app.services.platforms import get_platform
from app.services.platforms.base import PLATFORM_META

router = APIRouter()


def _to_read(p: PlatformAccount) -> PlatformAccountRead:
    data = PlatformAccountRead.model_validate(p).model_dump()
    data["has_credentials"] = bool(p.api_key or p.access_token)
    return PlatformAccountRead(**data)


@router.get("/meta")
def platform_meta() -> dict:
    return PLATFORM_META


@router.get("", response_model=list[PlatformAccountRead])
def list_accounts(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[PlatformAccountRead]:
    rows = db.query(PlatformAccount).filter_by(user_id=user.id).order_by(PlatformAccount.id.desc()).all()
    return [_to_read(r) for r in rows]


@router.post("", response_model=PlatformAccountRead)
def create_account(
    payload: PlatformAccountCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlatformAccountRead:
    p = PlatformAccount(user_id=user.id, **payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return _to_read(p)


@router.patch("/{account_id}", response_model=PlatformAccountRead)
def update_account(
    account_id: int,
    payload: PlatformAccountUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlatformAccountRead:
    p = db.query(PlatformAccount).filter_by(id=account_id, user_id=user.id).first()
    if not p:
        raise HTTPException(404, "Không tìm thấy account")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return _to_read(p)


@router.delete("/{account_id}")
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    p = db.query(PlatformAccount).filter_by(id=account_id, user_id=user.id).first()
    if not p:
        raise HTTPException(404, "Không tìm thấy account")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.post("/{account_id}/test")
def test_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    p = db.query(PlatformAccount).filter_by(id=account_id, user_id=user.id).first()
    if not p:
        raise HTTPException(404, "Không tìm thấy account")
    try:
        ok = get_platform(p.platform, p).test_connection()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    return {"ok": ok}


# ---------- Etsy OAuth ----------
@router.get("/etsy/oauth-start")
def etsy_oauth_start(user: User = Depends(get_current_user)) -> dict:
    if not settings.etsy_client_id:
        raise HTTPException(400, "Chưa cấu hình ETSY_CLIENT_ID")
    import secrets as pysecrets

    state = pysecrets.token_urlsafe(16)
    code_verifier = pysecrets.token_urlsafe(48)
    # In production, cache state+verifier in Redis keyed by user.id. For now, echo it back.
    url = (
        "https://www.etsy.com/oauth/connect?"
        f"response_type=code&client_id={settings.etsy_client_id}"
        f"&redirect_uri={settings.etsy_redirect_uri}"
        f"&scope=listings_r%20listings_w%20shops_r"
        f"&state={state}:{user.id}"
        f"&code_challenge={code_verifier}"
        f"&code_challenge_method=S256"
    )
    return {"authorize_url": url, "code_verifier": code_verifier}


@router.get("/etsy/callback")
def etsy_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    try:
        user_id = int(state.split(":")[1])
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "State không hợp lệ") from None

    r = httpx.post(
        "https://api.etsy.com/v3/public/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": settings.etsy_client_id,
            "redirect_uri": settings.etsy_redirect_uri,
            "code": code,
            "code_verifier": state,  # simplified — production should cache verifier
        },
        timeout=30,
    )
    if r.status_code != 200:
        raise HTTPException(400, f"Etsy OAuth lỗi: {r.text[:500]}")
    tok = r.json()
    expires_at = datetime.now(UTC) + timedelta(seconds=int(tok.get("expires_in", 3600)))

    acc = (
        db.query(PlatformAccount).filter_by(user_id=user_id, platform="etsy").first()
        or PlatformAccount(user_id=user_id, platform="etsy", label="Etsy")
    )
    acc.access_token = tok["access_token"]
    acc.refresh_token = tok.get("refresh_token")
    acc.token_expires_at = expires_at
    acc.is_active = True
    db.add(acc)
    db.commit()
    return RedirectResponse("/platforms?etsy=connected", status_code=302)
