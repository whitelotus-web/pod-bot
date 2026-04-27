from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class PlatformAccountBase(BaseModel):
    platform: str
    label: str = ""
    api_key: str | None = None
    shop_id: str | None = None
    extra: dict[str, Any] | None = None
    is_active: bool = True

    # Optional fingerprint + warmup overrides at creation
    proxy_url: str | None = None
    user_agent: str | None = None
    account_age_days_override: int | None = None
    daily_publish_cap_override: int | None = None


class PlatformAccountCreate(PlatformAccountBase):
    pass


class PlatformAccountUpdate(BaseModel):
    label: str | None = None
    api_key: str | None = None
    shop_id: str | None = None
    extra: dict[str, Any] | None = None
    is_active: bool | None = None
    proxy_url: str | None = None
    user_agent: str | None = None
    account_age_days_override: int | None = None
    daily_publish_cap_override: int | None = None


class PlatformAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    platform: str
    label: str
    shop_id: str | None
    has_credentials: bool = False
    is_active: bool
    proxy_url: str | None = None
    user_agent: str | None = None
    account_age_days_override: int | None = None
    daily_publish_cap_override: int | None = None
    health_status: str | None = "healthy"
    created_at: datetime
    updated_at: datetime
