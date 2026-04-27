from fastapi import APIRouter

from app.api.v1 import (
    ai_keys,
    auth,
    campaigns,
    catalog,
    designs,
    keywords,
    mockups,
    platforms,
    products,
    prompts,
    runs,
    seo,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])
api_router.include_router(keywords.router, prefix="/keywords", tags=["keywords"])
api_router.include_router(designs.router, prefix="/designs", tags=["designs"])
api_router.include_router(mockups.router, prefix="/mockups", tags=["mockups"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(platforms.router, prefix="/platforms", tags=["platforms"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(ai_keys.router, prefix="/ai-keys", tags=["ai-keys"])
api_router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
api_router.include_router(catalog.router, prefix="/catalog", tags=["catalog"])
api_router.include_router(seo.router, prefix="/seo", tags=["seo"])
