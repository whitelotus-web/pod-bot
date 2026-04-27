"""Prompt template library + live preview + ad-hoc generation."""
from __future__ import annotations

import base64
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from slugify import slugify
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models import Design, User
from app.services.ai import GeneratedImage
from app.services.ai.base import get_engine_for_user
from app.services.prompts import TEMPLATES, compose_preview

router = APIRouter()


class TemplateRead(BaseModel):
    id: str
    label: str
    description: str
    style: str
    sample_prompt: str


class PreviewRequest(BaseModel):
    keyword: str = Field(..., min_length=1)
    niche: str = ""
    style: str = ""


class PreviewResponse(BaseModel):
    final_prompt: str


class GenerateRequest(BaseModel):
    keyword: str = Field(..., min_length=1)
    niche: str = ""
    style: str = ""
    engine: str = "gemini"
    persist: bool = True  # if True, save Design row + file in /media


class GenerateResponse(BaseModel):
    final_prompt: str
    image_base64: str | None = None
    file_path: str | None = None
    design_id: int | None = None
    engine: str
    model: str | None


@router.get("/templates", response_model=list[TemplateRead])
def list_templates() -> list[TemplateRead]:
    return [TemplateRead(**t.__dict__) for t in TEMPLATES]


@router.post("/preview", response_model=PreviewResponse)
def preview_prompt(payload: PreviewRequest) -> PreviewResponse:
    final = compose_preview(payload.keyword, payload.niche, payload.style)
    return PreviewResponse(final_prompt=final)


@router.post("/generate", response_model=GenerateResponse)
def generate_one(
    payload: GenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GenerateResponse:
    engine = get_engine_for_user(payload.engine, user.id, db)
    final = compose_preview(payload.keyword, payload.niche, payload.style)
    try:
        img: GeneratedImage = engine.generate(final)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"AI generate failed: {exc}") from exc

    if not payload.persist:
        return GenerateResponse(
            final_prompt=final,
            image_base64=base64.b64encode(img.image_bytes).decode("ascii"),
            file_path=None,
            design_id=None,
            engine=payload.engine,
            model=img.model,
        )

    Path(settings.media_root, "designs").mkdir(parents=True, exist_ok=True)
    fname = f"adhoc_{user.id}_{slugify(payload.keyword)[:40]}_{int(__import__('time').time())}.png"
    fpath = Path(settings.media_root, "designs", fname)
    fpath.write_bytes(img.image_bytes)
    rel = str(fpath.relative_to(settings.media_root))
    design = Design(
        campaign_id=None,
        keyword_id=None,
        title=payload.keyword.title(),
        prompt=final,
        engine=payload.engine,
        model=img.model,
        file_path=rel,
        status="ready",
    )
    db.add(design)
    db.commit()
    db.refresh(design)
    return GenerateResponse(
        final_prompt=final,
        image_base64=None,
        file_path=rel,
        design_id=design.id,
        engine=payload.engine,
        model=img.model,
    )
