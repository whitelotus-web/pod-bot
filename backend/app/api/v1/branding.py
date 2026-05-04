"""Shop branding generator endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models import User
from app.services.shop_branding import generate

router = APIRouter()


class BrandingRequest(BaseModel):
    niche: str


@router.post("/generate")
def generate_branding(
    payload: BrandingRequest,
    _: User = Depends(get_current_user),
) -> dict:
    pack = generate(payload.niche)
    return {
        "banner_prompt": pack.banner_prompt,
        "logo_prompt": pack.logo_prompt,
        "about_section": pack.about_section,
        "announcement": pack.announcement,
        "policies": pack.policies,
        "shop_sections": pack.shop_sections,
        "source": pack.source,
    }
