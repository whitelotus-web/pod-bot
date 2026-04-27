"""User-managed AI API keys (encrypted at rest) + test-connection."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.crypto import decrypt, encrypt, mask
from app.models import AIKey, User
from app.schemas.ai_key import AIKeyCreate, AIKeyRead, AIKeyTestRequest, AIKeyTestResponse
from app.services.ai import get_engine

router = APIRouter()

SUPPORTED = ("gemini", "openai", "replicate")


def _to_read(row: AIKey) -> AIKeyRead:
    plain = decrypt(row.encrypted_key)
    return AIKeyRead(
        id=row.id,
        engine=row.engine,
        label=row.label,
        masked_key=mask(plain),
        is_active=row.is_active,
        created_at=row.created_at,
    )


@router.get("", response_model=list[AIKeyRead])
def list_keys(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AIKeyRead]:
    rows = db.query(AIKey).filter_by(user_id=user.id).order_by(AIKey.id.desc()).all()
    return [_to_read(r) for r in rows]


@router.post("", response_model=AIKeyRead, status_code=201)
def create_key(
    payload: AIKeyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AIKeyRead:
    engine = payload.engine.lower()
    if engine not in SUPPORTED:
        raise HTTPException(400, f"Engine không hỗ trợ: {engine}")
    row = AIKey(
        user_id=user.id,
        engine=engine,
        label=payload.label or engine.title(),
        encrypted_key=encrypt(payload.api_key.strip()),
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_read(row)


@router.delete("/{key_id}", status_code=204)
def delete_key(
    key_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    row = db.get(AIKey, key_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Không tìm thấy key")
    db.delete(row)
    db.commit()


@router.post("/test", response_model=AIKeyTestResponse)
def test_connection(
    payload: AIKeyTestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AIKeyTestResponse:
    engine_name = payload.engine.lower()
    if engine_name not in SUPPORTED:
        raise HTTPException(400, f"Engine không hỗ trợ: {engine_name}")
    api_key = payload.api_key
    if not api_key:
        row = (
            db.query(AIKey)
            .filter_by(user_id=user.id, engine=engine_name, is_active=True)
            .order_by(AIKey.id.desc())
            .first()
        )
        if row:
            api_key = decrypt(row.encrypted_key)
    engine = get_engine(engine_name, api_key=api_key)
    ok, message = engine.test_connection()
    return AIKeyTestResponse(ok=ok, message=message)
