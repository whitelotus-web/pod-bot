from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class KeywordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    campaign_id: int | None
    term: str
    source: str
    score: float
    rank: int
    raw: dict[str, Any] | None = None
    fetched_at: datetime
