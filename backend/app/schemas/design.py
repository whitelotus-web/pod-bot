from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DesignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    campaign_id: int | None
    keyword_id: int | None
    title: str
    prompt: str
    engine: str
    model: str | None
    file_path: str
    thumbnail_path: str | None
    width: int | None
    height: int | None
    status: str
    created_at: datetime
