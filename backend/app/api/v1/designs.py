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


@router.post("/{design_id}/regenerate", response_model=DesignRead)
def regenerate_design(
    design_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DesignRead:
    """Re-run the AI engine with the same prompt and replace the image file.

    Useful in semi-auto review mode when a user doesn't like the first output
    but wants to keep prompt + metadata.
    """
    from pathlib import Path

    from app.core.config import settings
    from app.services.ai.base import get_engine_for_user

    d = db.get(Design, design_id)
    if not d:
        raise HTTPException(404, "Không tìm thấy design")

    engine = get_engine_for_user(d.engine, user.id, db)
    try:
        img = engine.generate(d.prompt, model=d.model)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"AI generate failed: {exc}") from exc

    fpath = Path(settings.media_root) / d.file_path
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_bytes(img.image_bytes)
    d.status = "ready"
    db.commit()
    db.refresh(d)
    return DesignRead.model_validate(d)


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
