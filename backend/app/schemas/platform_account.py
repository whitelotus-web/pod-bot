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


class PlatformAccountCreate(PlatformAccountBase):
    pass


class PlatformAccountUpdate(BaseModel):
    label: str | None = None
    api_key: str | None = None
    shop_id: str | None = None
    extra: dict[str, Any] | None = None
    is_active: bool | None = None


class PlatformAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    platform: str
    label: str
    shop_id: str | None
    has_credentials: bool = False
    is_active: bool
    created_at: datetime
    updated_at: datetime
