"""Art-school prompt template library — list + render preview."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models import User
from app.services.prompt_templates import by_id, families, list_all, render

router = APIRouter()


class TemplatePreviewRequest(BaseModel):
    template_id: str
    niche: str = ""
    keyword: str = ""


@router.get("")
def list_templates(_: User = Depends(get_current_user)) -> dict:
    return {"families": families(), "templates": list_all()}


@router.post("/preview", response_model=dict)
def preview(
    payload: TemplatePreviewRequest, _: User = Depends(get_current_user)
) -> dict:
    if by_id(payload.template_id) is None:
        raise HTTPException(404, "Template không tồn tại")
    rendered = render(
        payload.template_id, niche=payload.niche, keyword=payload.keyword
    )
    return {"template_id": payload.template_id, "rendered": rendered}
