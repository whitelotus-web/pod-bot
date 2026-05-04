"""User-managed AI API keys (encrypted at rest) + test-connection."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.crypto import decrypt, encrypt, mask
from app.models import AIKey, User
from app.models.ai_key import ROLES
from app.schemas.ai_key import (
    AIKeyCreate,
    AIKeyRead,
    AIKeyTestRequest,
    AIKeyTestResponse,
    AIKeyUpdate,
)
from app.services.ai import get_engine
from app.services.ai_router import ROLE_ENGINES

router = APIRouter()

SUPPORTED = ("gemini", "openai", "replicate")


def _to_read(row: AIKey) -> AIKeyRead:
    plain = decrypt(row.encrypted_key)
    return AIKeyRead(
        id=row.id,
        role=row.role,
        engine=row.engine,
        label=row.label,
        masked_key=mask(plain),
        is_active=row.is_active,
        priority=row.priority,
        quota_failures=row.quota_failures,
        last_used_at=row.last_used_at,
        created_at=row.created_at,
    )


def _validate_role_engine(role: str, engine: str) -> None:
    if role not in ROLES:
        raise HTTPException(400, f"Role không hỗ trợ: {role}")
    allowed = ROLE_ENGINES.get(role, [])
    if engine not in allowed:
        raise HTTPException(
            400, f"Engine '{engine}' không phù hợp với role '{role}'. Cho phép: {allowed}"
        )


@router.get("/roles")
def list_roles() -> dict:
    """Return role catalog with allowed engines for the UI."""
    return {
        "roles": [
            {
                "id": "image_generation",
                "label": "Sinh design (image)",
                "description": "AI vẽ ra file PNG transparent cho design.",
                "engines": ROLE_ENGINES["image_generation"],
            },
            {
                "id": "seo_writer",
                "label": "Viết SEO (text)",
                "description": "AI viết tiêu đề, mô tả, tag Etsy cho từng sản phẩm.",
                "engines": ROLE_ENGINES["seo_writer"],
            },
            {
                "id": "keyword_expansion",
                "label": "Mở rộng keyword (text)",
                "description": "AI gợi ý long-tail keyword từ niche gốc.",
                "engines": ROLE_ENGINES["keyword_expansion"],
            },
        ],
    }


@router.get("", response_model=list[AIKeyRead])
def list_keys(
    role: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AIKeyRead]:
    q = db.query(AIKey).filter_by(user_id=user.id)
    if role:
        q = q.filter(AIKey.role == role)
    rows = q.order_by(AIKey.role.asc(), AIKey.priority.asc(), AIKey.id.desc()).all()
    return [_to_read(r) for r in rows]


@router.post("", response_model=AIKeyRead, status_code=201)
def create_key(
    payload: AIKeyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AIKeyRead:
    engine = payload.engine.lower()
    role = payload.role
    if engine not in SUPPORTED:
        raise HTTPException(400, f"Engine không hỗ trợ: {engine}")
    _validate_role_engine(role, engine)

    row = AIKey(
        user_id=user.id,
        role=role,
        engine=engine,
        label=payload.label or f"{engine.title()} ({role})",
        encrypted_key=encrypt(payload.api_key.strip()),
        is_active=True,
        priority=max(1, int(payload.priority)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_read(row)


@router.patch("/{key_id}", response_model=AIKeyRead)
def update_key(
    key_id: int,
    payload: AIKeyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AIKeyRead:
    row = db.get(AIKey, key_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Không tìm thấy key")
    if payload.role is not None:
        _validate_role_engine(payload.role, row.engine)
        row.role = payload.role
    if payload.label is not None:
        row.label = payload.label
    if payload.is_active is not None:
        row.is_active = payload.is_active
    if payload.priority is not None:
        row.priority = max(1, int(payload.priority))
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
        q = db.query(AIKey).filter_by(user_id=user.id, engine=engine_name, is_active=True)
        if payload.role:
            q = q.filter(AIKey.role == payload.role)
        row = q.order_by(AIKey.priority.asc(), AIKey.id.desc()).first()
        if row:
            api_key = decrypt(row.encrypted_key)
    engine = get_engine(engine_name, api_key=api_key)
    ok, message = engine.test_connection()
    return AIKeyTestResponse(ok=ok, message=message)
