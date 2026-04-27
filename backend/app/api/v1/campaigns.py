from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Campaign, User
from app.schemas.campaign import CampaignCreate, CampaignRead, CampaignUpdate

router = APIRouter()


@router.get("", response_model=list[CampaignRead])
def list_campaigns(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[CampaignRead]:
    rows = db.query(Campaign).filter_by(user_id=user.id).order_by(Campaign.id.desc()).all()
    return [CampaignRead.model_validate(r) for r in rows]


@router.post("", response_model=CampaignRead)
def create_campaign(
    payload: CampaignCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CampaignRead:
    c = Campaign(user_id=user.id, **payload.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return CampaignRead.model_validate(c)


@router.get("/{campaign_id}", response_model=CampaignRead)
def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CampaignRead:
    c = db.query(Campaign).filter_by(id=campaign_id, user_id=user.id).first()
    if not c:
        raise HTTPException(404, "Không tìm thấy campaign")
    return CampaignRead.model_validate(c)


@router.patch("/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CampaignRead:
    c = db.query(Campaign).filter_by(id=campaign_id, user_id=user.id).first()
    if not c:
        raise HTTPException(404, "Không tìm thấy campaign")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return CampaignRead.model_validate(c)


@router.delete("/{campaign_id}")
def delete_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    c = db.query(Campaign).filter_by(id=campaign_id, user_id=user.id).first()
    if not c:
        raise HTTPException(404, "Không tìm thấy campaign")
    db.delete(c)
    db.commit()
    return {"ok": True}


@router.post("/{campaign_id}/run")
def run_now(
    campaign_id: int,
    force_auto: bool | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    c = db.query(Campaign).filter_by(id=campaign_id, user_id=user.id).first()
    if not c:
        raise HTTPException(404, "Không tìm thấy campaign")
    from app.workers.celery_app import celery_app
    async_result = celery_app.send_task(
        "app.workers.pipeline.run_campaign", args=[campaign_id, force_auto]
    )
    return {"task_id": async_result.id, "campaign_id": campaign_id}
