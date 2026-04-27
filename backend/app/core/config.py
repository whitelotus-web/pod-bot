"""Typed settings loaded from environment variables (.env)."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Core ---
    app_name: str = "POD Bot"
    environment: str = Field(default="development")
    secret_key: str = Field(default="change-me-change-me-change-me-change-me")
    access_token_expire_minutes: int = 43200  # 30 days

    # --- DB / cache ---
    database_url: str = Field(default="postgresql+psycopg://podbot:podbot@postgres:5432/podbot")
    redis_url: str = Field(default="redis://redis:6379/0")
    celery_broker_url: str = Field(default="redis://redis:6379/1")
    celery_result_backend: str = Field(default="redis://redis:6379/2")

    # --- Default admin ---
    admin_email: str = "admin@podbot.local"
    admin_password: str = "admin123"

    # --- AI ---
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    replicate_api_token: str | None = None

    # --- POD platforms ---
    printify_api_key: str | None = None
    printify_shop_id: str | None = None
    printful_api_key: str | None = None
    etsy_client_id: str | None = None
    etsy_client_secret: str | None = None
    etsy_redirect_uri: str = "http://localhost:8000/api/v1/platforms/etsy/callback"

    # --- Keyword sources ---
    pinterest_cookie: str | None = None
    tiktok_cookie: str | None = None

    # --- Media ---
    media_root: str = "/app/media"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
