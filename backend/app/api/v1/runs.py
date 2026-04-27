from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Campaign, RunLog, User
from app.schemas.run_log import RunLogRead

router = APIRouter()


@router.get("", response_model=list[RunLogRead])
def list_runs(
    campaign_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[RunLogRead]:
    q = db.query(RunLog).join(Campaign, RunLog.campaign_id == Campaign.id, isouter=True)
    q = q.filter((Campaign.user_id == user.id) | (RunLog.campaign_id.is_(None)))
    if campaign_id:
        q = q.filter(RunLog.campaign_id == campaign_id)
    rows = q.order_by(RunLog.id.desc()).limit(limit).all()
    return [RunLogRead.model_validate(r) for r in rows]
