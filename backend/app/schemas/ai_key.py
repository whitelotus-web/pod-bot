"""Schemas for AI API key management."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AIKeyCreate(BaseModel):
    engine: str = Field(..., description="gemini | openai | replicate")
    label: str = ""
    api_key: str = Field(..., min_length=10)


class AIKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    engine: str
    label: str
    masked_key: str
    is_active: bool
    created_at: datetime


class AIKeyTestRequest(BaseModel):
    engine: str
    api_key: str | None = None  # if missing, test the saved key for the user


class AIKeyTestResponse(BaseModel):
    ok: bool
    message: str
