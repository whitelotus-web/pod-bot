"""Quality gate endpoints — run checks on a saved design."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models import Design, User
from app.services.quality import evaluate_design

router = APIRouter()


@router.post("/designs/{design_id}/evaluate")
def evaluate(
    design_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    d = db.get(Design, design_id)
    if not d:
        raise HTTPException(404, "Design không tồn tại")
    if d.campaign and d.campaign.user_id != user.id:
        raise HTTPException(403, "Không có quyền")

    rel = d.bg_removed_path or d.file_path
    abs_path = Path(settings.media_root) / rel
    if not abs_path.exists():
        raise HTTPException(404, "File design không tồn tại trên đĩa")

    keyword = d.keyword.term if d.keyword else d.title
    report = evaluate_design(str(abs_path), expected_keyword=keyword)

    d.quality_score = report.overall_score
    d.quality_report = report.to_dict()
    if report.rejected:
        d.status = "rejected"
        d.rejection_reason = report.rejection_reason
    db.commit()

    return report.to_dict()
