"""A/B variant test endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Campaign, User
from app.services import ab_test as ab_service
from app.services.audit import log_action

router = APIRouter()


class VariantOverride(BaseModel):
    style_prompt: str | None = None
    ai_engine: str | None = None
    ai_model: str | None = None
    designs_per_keyword: int | None = None
    base_price_usd: float | None = None
    prompt_template_ids: list[int] | None = None


class CreateRequest(BaseModel):
    campaign_id: int
    overrides: list[VariantOverride] = Field(..., min_length=1, max_length=24)


class PickWinnerRequest(BaseModel):
    group_id: str
    min_orders_per_variant: int = 5


def _own_campaign(db: Session, user: User, campaign_id: int) -> Campaign:
    c = db.query(Campaign).filter_by(id=campaign_id, user_id=user.id).first()
    if c is None:
        raise HTTPException(status_code=404, detail="Campaign không tồn tại.")
    return c


@router.post("/create")
def create(
    body: CreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    parent = _own_campaign(db, user, body.campaign_id)
    variants = ab_service.create_variants(
        db,
        parent,
        overrides=[o.model_dump(exclude_none=True) for o in body.overrides],
    )
    log_action(
        db,
        user_id=user.id,
        action="ab_test.create",
        target_type="campaign",
        target_id=parent.id,
        payload={"group_id": parent.ab_test_group, "variants": len(variants) + 1},
    )
    return {
        "group_id": parent.ab_test_group,
        "parent": {"id": parent.id, "label": parent.ab_variant_label},
        "variants": [
            {"id": v.id, "label": v.ab_variant_label, "name": v.name} for v in variants
        ],
    }


@router.get("/{group_id}")
def measure(
    group_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    # Confirm the group belongs to the user before exposing performance data.
    own = (
        db.query(Campaign)
        .filter_by(ab_test_group=group_id, user_id=user.id)
        .first()
    )
    if own is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy A/B group.")
    perfs = ab_service.measure(db, group_id)
    return {
        "group_id": group_id,
        "variants": [p.to_dict() for p in perfs],
    }


@router.post("/pick-winner")
def pick_winner(
    body: PickWinnerRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    own = (
        db.query(Campaign)
        .filter_by(ab_test_group=body.group_id, user_id=user.id)
        .first()
    )
    if own is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy A/B group.")
    winner = ab_service.pick_winner(
        db, body.group_id, min_orders_per_variant=body.min_orders_per_variant
    )
    if winner is None:
        return {"concluded": False, "reason": "Chưa đủ dữ liệu để chốt winner."}
    log_action(
        db,
        user_id=user.id,
        action="ab_test.pick_winner",
        target_type="ab_test_group",
        target_id=None,
        payload={"group_id": body.group_id, "winner": winner.to_dict()},
    )
    return {"concluded": True, "winner": winner.to_dict()}
