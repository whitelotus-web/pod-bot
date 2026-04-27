"""Google Gemini image-gen via `google-genai`.

Model: `gemini-2.5-flash-image-preview` (aka "Imagen / Nano Banana").
Docs: https://ai.google.dev/gemini-api/docs/image-generation
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.services.ai.base import AIDesignEngine, GeneratedImage

logger = logging.getLogger(__name__)


class GeminiEngine(AIDesignEngine):
    name = "gemini"
    default_model = "gemini-2.5-flash-image"

    def generate(self, prompt: str, model: str | None = None, size: str = "1024x1024") -> GeneratedImage:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY chưa được cấu hình")

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("Cần cài google-genai: pip install google-genai") from exc

        client = genai.Client(api_key=settings.gemini_api_key)
        model_id = model or self.default_model

        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
        )

        for part in response.candidates[0].content.parts:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                return GeneratedImage(
                    image_bytes=part.inline_data.data,
                    mime_type=part.inline_data.mime_type or "image/png",
                    prompt=prompt,
                    model=model_id,
                )
        raise RuntimeError(f"Gemini không trả về ảnh. Response: {response}")
