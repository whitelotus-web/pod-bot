from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class RunLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    campaign_id: int | None
    stage: str
    status: str
    message: str | None
    data: dict[str, Any] | None = None
    started_at: datetime
    finished_at: datetime | None
