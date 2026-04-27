from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MockupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    design_id: int
    product_type: str
    template: str
    file_path: str
    created_at: datetime
