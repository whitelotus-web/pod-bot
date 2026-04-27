from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Mockup, User
from app.schemas.mockup import MockupRead
from app.services.mockup import PillowMockup

router = APIRouter()


@router.get("/templates")
def list_templates() -> list[str]:
    return PillowMockup().available_templates()


@router.get("", response_model=list[MockupRead])
def list_mockups(
    design_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),  # noqa: ARG001
) -> list[MockupRead]:
    q = db.query(Mockup)
    if design_id:
        q = q.filter_by(design_id=design_id)
    return [MockupRead.model_validate(r) for r in q.order_by(Mockup.id.desc()).limit(200).all()]
