from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CampaignBase(BaseModel):
    name: str
    niche: str = ""
    style_prompt: str = ""
    # Default to the most reliable free sources
    keyword_sources: list[str] = Field(default_factory=lambda: ["google_trends", "etsy"])
    ai_engine: str = "gemini"
    ai_model: str | None = None
    designs_per_keyword: int = 2
    product_types: list[str] = Field(
        default_factory=lambda: ["tshirt_unisex", "hoodie", "mug_11oz"]
    )
    base_price_usd: float = 19.99
    auto_mode: str = "semi"
    # Default: Printify is core (auto-syncs to Etsy if shop is connected)
    target_platforms: list[str] = Field(default_factory=lambda: ["printify"])
    target_account_ids: list[int] = Field(default_factory=list)
    seo_auto: bool = True
    schedule_cron: str | None = None
    is_active: bool = True


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(BaseModel):
    name: str | None = None
    niche: str | None = None
    style_prompt: str | None = None
    keyword_sources: list[str] | None = None
    ai_engine: str | None = None
    ai_model: str | None = None
    designs_per_keyword: int | None = None
    product_types: list[str] | None = None
    base_price_usd: float | None = None
    auto_mode: str | None = None
    target_platforms: list[str] | None = None
    target_account_ids: list[int] | None = None
    seo_auto: bool | None = None
    schedule_cron: str | None = None
    is_active: bool | None = None


class CampaignRead(CampaignBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    last_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
