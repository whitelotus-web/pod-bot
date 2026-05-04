"""Schemas for AI API key management."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AIKeyCreate(BaseModel):
    engine: str = Field(..., description="gemini | openai | replicate")
    role: str = Field("image_generation", description="image_generation | seo_writer | keyword_expansion")
    label: str = ""
    api_key: str = Field(..., min_length=10)
    priority: int = 1


class AIKeyUpdate(BaseModel):
    label: str | None = None
    is_active: bool | None = None
    priority: int | None = None
    role: str | None = None


class AIKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    engine: str
    label: str
    masked_key: str
    is_active: bool
    priority: int
    quota_failures: int
    last_used_at: datetime | None
    created_at: datetime


class AIKeyTestRequest(BaseModel):
    engine: str
    api_key: str | None = None  # if missing, test the saved key for the user
    role: str | None = None  # optional filter: when set, tests the saved key matching this role


class AIKeyTestResponse(BaseModel):
    ok: bool
    message: str
