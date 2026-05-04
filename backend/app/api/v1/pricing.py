"""Dynamic pricing rule CRUD."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import PricingRule, User

router = APIRouter()


class RuleIn(BaseModel):
    name: str
    trigger: str  # high_momentum | weekend_flash | low_ctr_discount
    delta_usd: float = 0.0
    delta_percent: float = 0.0
    min_price_usd: float = 0.0
    max_price_usd: float | None = None
    is_active: bool = True


_ALLOWED = {"high_momentum", "weekend_flash", "low_ctr_discount"}


@router.get("")
def list_rules(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    rows = (
        db.query(PricingRule)
        .filter(PricingRule.user_id == user.id)
        .order_by(PricingRule.id.asc())
        .all()
    )
    return [
        {
            "id": r.id,
            "name": r.name,
            "trigger": r.trigger,
            "delta_usd": r.delta_usd,
            "delta_percent": r.delta_percent,
            "min_price_usd": r.min_price_usd,
            "max_price_usd": r.max_price_usd,
            "is_active": r.is_active,
        }
        for r in rows
    ]


@router.post("")
def create_rule(
    payload: RuleIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if payload.trigger not in _ALLOWED:
        raise HTTPException(400, f"trigger phải thuộc {_ALLOWED}")
    row = PricingRule(
        user_id=user.id,
        name=payload.name[:128],
        trigger=payload.trigger,
        delta_usd=payload.delta_usd,
        delta_percent=payload.delta_percent,
        min_price_usd=payload.min_price_usd,
        max_price_usd=payload.max_price_usd,
        is_active=payload.is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.patch("/{rule_id}")
def update_rule(
    rule_id: int,
    payload: RuleIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    r = db.get(PricingRule, rule_id)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Không tìm thấy")
    if payload.trigger not in _ALLOWED:
        raise HTTPException(400, "trigger không hợp lệ")
    r.name = payload.name[:128]
    r.trigger = payload.trigger
    r.delta_usd = payload.delta_usd
    r.delta_percent = payload.delta_percent
    r.min_price_usd = payload.min_price_usd
    r.max_price_usd = payload.max_price_usd
    r.is_active = payload.is_active
    db.commit()
    return {"ok": True}


@router.delete("/{rule_id}")
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    r = db.get(PricingRule, rule_id)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Không tìm thấy")
    db.delete(r)
    db.commit()
    return {"ok": True}
