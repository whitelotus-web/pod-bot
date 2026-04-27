from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    design_id: int
    platform_account_id: int
    external_id: str | None
    url: str | None
    title: str
    description: str
    tags: list[str]
    price_usd: float
    status: str
    error: str | None
    created_at: datetime
    published_at: datetime | None
