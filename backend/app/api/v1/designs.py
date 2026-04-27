from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Campaign, Design, User
from app.schemas.design import DesignRead

router = APIRouter()


@router.get("", response_model=list[DesignRead])
def list_designs(
    campaign_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DesignRead]:
    q = db.query(Design).join(Campaign, Design.campaign_id == Campaign.id, isouter=True).filter(
        (Campaign.user_id == user.id) | (Design.campaign_id.is_(None))
    )
    if campaign_id:
        q = q.filter(Design.campaign_id == campaign_id)
    rows = q.order_by(Design.id.desc()).limit(200).all()
    return [DesignRead.model_validate(r) for r in rows]


@router.post("/{design_id}/approve")
def approve_design(
    design_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),  # noqa: ARG001
) -> dict:
    d = db.get(Design, design_id)
    if not d:
        raise HTTPException(404, "Không tìm thấy design")
    d.status = "approved"
    db.commit()
    return {"ok": True}


@router.post("/{design_id}/reject")
def reject_design(
    design_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),  # noqa: ARG001
) -> dict:
    d = db.get(Design, design_id)
    if not d:
        raise HTTPException(404, "Không tìm thấy design")
    d.status = "rejected"
    db.commit()
    return {"ok": True}


@router.post("/{design_id}/publish")
def publish_design(
    design_id: int,
    platform: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Publish a single design on demand to a specific platform."""
    from app.models import PlatformAccount
    from app.services.platforms import get_platform

    d = db.get(Design, design_id)
    if not d:
        raise HTTPException(404, "Không tìm thấy design")
    account = (
        db.query(PlatformAccount)
        .filter_by(user_id=user.id, platform=platform, is_active=True)
        .first()
    )
    if not account:
        raise HTTPException(400, f"Chưa kết nối tài khoản {platform}")
    from pathlib import Path

    from app.core.config import settings
    from app.models import Product

    adapter = get_platform(platform, account)
    design_abs = str(Path(settings.media_root) / d.file_path)
    res = adapter.publish(
        design_path=design_abs,
        title=d.title,
        description=f"{d.title} — thiết kế độc đáo, in theo yêu cầu.",
        tags=[d.title.lower()],
        price_usd=19.99,
    )
    product = Product(
        design_id=d.id,
        platform_account_id=account.id,
        external_id=res.external_id,
        url=res.url,
        title=d.title,
        description="",
        tags=[],
        price_usd=19.99,
        status=res.status,
        error=res.error,
    )
    db.add(product)
    db.commit()
    return {
        "ok": res.status == "published",
        "status": res.status,
        "url": res.url,
        "error": res.error,
    }
