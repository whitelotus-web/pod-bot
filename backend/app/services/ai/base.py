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


def get_engine(name: str) -> AIDesignEngine:
    from app.services.ai.gemini import GeminiEngine
    from app.services.ai.openai_engine import OpenAIDalleEngine
    from app.services.ai.replicate_engine import ReplicateEngine

    name = (name or "gemini").lower()
    if name == "gemini":
        return GeminiEngine()
    if name in ("openai", "dalle", "dall-e"):
        return OpenAIDalleEngine()
    if name == "replicate":
        return ReplicateEngine()
    raise ValueError(f"Unknown AI engine: {name}")
