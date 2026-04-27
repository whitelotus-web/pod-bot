"""SEO writer endpoints: per-product title/tags/description generation."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Design, Product, User
from app.services.catalog import get_blueprint
from app.services.seo import generate_seo, suggest_shop_names

router = APIRouter()


class SEORequest(BaseModel):
    keyword: str
    niche: str = ""
    product_id: str = "tshirt_unisex"


class SEOResponse(BaseModel):
    title: str
    description: str
    tags: list[str]
    source: str


@router.post("/generate", response_model=SEOResponse)
def generate(
    payload: SEORequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SEOResponse:
    if not get_blueprint(payload.product_id):
        raise HTTPException(400, f"Product không có trong catalog: {payload.product_id}")
    out = generate_seo(
        keyword=payload.keyword,
        niche=payload.niche or payload.keyword,
        product_id=payload.product_id,
        user_id=user.id,
        db=db,
    )
    return SEOResponse(
        title=out.title, description=out.description, tags=out.tags, source=out.source
    )


class DesignSEORequest(BaseModel):
    product_id: str = "tshirt_unisex"


@router.post("/designs/{design_id}", response_model=SEOResponse)
def generate_for_design(
    design_id: int,
    payload: DesignSEORequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SEOResponse:
    """Generate SEO using a saved design's title + campaign niche."""
    d = db.get(Design, design_id)
    if not d:
        raise HTTPException(404, "Design không tồn tại")
    if d.campaign and d.campaign.user_id != user.id:
        raise HTTPException(403, "Không có quyền")
    niche = d.campaign.niche if d.campaign else d.title
    out = generate_seo(
        keyword=d.title,
        niche=niche or d.title,
        product_id=payload.product_id,
        user_id=user.id,
        db=db,
    )
    return SEOResponse(
        title=out.title, description=out.description, tags=out.tags, source=out.source
    )


class ProductSEOPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None


@router.patch("/products/{product_id}", response_model=dict)
def patch_product_seo(
    product_id: int,
    payload: ProductSEOPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(404, "Product không tồn tại")
    # Ownership: through design.campaign.user_id
    if p.design and p.design.campaign and p.design.campaign.user_id != user.id:
        raise HTTPException(403, "Không có quyền")
    if payload.title is not None:
        p.title = payload.title[:255]
    if payload.description is not None:
        p.description = payload.description
    if payload.tags is not None:
        p.tags = [t.strip()[:20] for t in payload.tags if t.strip()][:13]
    db.commit()
    return {"ok": True}


class ShopSuggestRequest(BaseModel):
    niche: str
    count: int = 6


class ShopSuggestResponse(BaseModel):
    names: list[str]


@router.post("/shop-names", response_model=ShopSuggestResponse)
def shop_names(
    payload: ShopSuggestRequest,
    _: User = Depends(get_current_user),
) -> ShopSuggestResponse:
    return ShopSuggestResponse(names=suggest_shop_names(payload.niche, payload.count))
