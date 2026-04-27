"""Abstract AI design engine + factory."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GeneratedImage:
    image_bytes: bytes
    mime_type: str = "image/png"
    prompt: str = ""
    model: str = ""


class AIDesignEngine(ABC):
    name: str = "base"

    def __init__(self, api_key: str | None = None) -> None:
        # Optional override; engines fall back to env-var settings if None.
        self.api_key_override = api_key

    @abstractmethod
    def generate(self, prompt: str, model: str | None = None, size: str = "1024x1024") -> GeneratedImage:
        ...

    def design_prompt(self, keyword: str, niche: str, style: str) -> str:
        """Build a 'print-ready t-shirt design' prompt from keyword + niche + style."""
        style = style or "clean vector illustration, bold typography, vibrant colors"
        niche_line = f"for the {niche} niche" if niche else ""
        return (
            f"T-shirt graphic design about '{keyword}' {niche_line}. "
            f"Style: {style}. "
            "Centered composition, transparent background, high contrast, no mockup, "
            "no photo realism, suitable for print-on-demand apparel, no watermark, no text artifacts."
        )


def get_engine(name: str, api_key: str | None = None) -> AIDesignEngine:
    from app.services.ai.gemini import GeminiEngine
    from app.services.ai.openai_engine import OpenAIDalleEngine
    from app.services.ai.replicate_engine import ReplicateEngine

    name = (name or "gemini").lower()
    if name == "gemini":
        return GeminiEngine(api_key=api_key)
    if name in ("openai", "dalle", "dall-e"):
        return OpenAIDalleEngine(api_key=api_key)
    if name == "replicate":
        return ReplicateEngine(api_key=api_key)
    raise ValueError(f"Unknown AI engine: {name}")


def get_engine_for_user(name: str, user_id: int, db) -> AIDesignEngine:
    """Pick the user's saved key for `name` if any, else fall back to env."""
    from app.core.crypto import decrypt
    from app.models import AIKey

    row = (
        db.query(AIKey)
        .filter_by(user_id=user_id, engine=name, is_active=True)
        .order_by(AIKey.id.desc())
        .first()
    )
    api_key = decrypt(row.encrypted_key) if row else None
    return get_engine(name, api_key=api_key)
