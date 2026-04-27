"""OpenAI DALL-E 3 / gpt-image-1."""
from __future__ import annotations

import base64
import logging

import httpx

from app.core.config import settings
from app.services.ai.base import AIDesignEngine, GeneratedImage

logger = logging.getLogger(__name__)


class OpenAIDalleEngine(AIDesignEngine):
    name = "openai"
    default_model = "gpt-image-1"

    def generate(self, prompt: str, model: str | None = None, size: str = "1024x1024") -> GeneratedImage:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY chưa được cấu hình")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Cần cài openai: pip install openai") from exc

        client = OpenAI(api_key=settings.openai_api_key)
        model_id = model or self.default_model

        resp = client.images.generate(
            model=model_id,
            prompt=prompt,
            size=size,
            n=1,
            response_format="b64_json" if model_id.startswith("dall") else None,
        )
        data = resp.data[0]
        if getattr(data, "b64_json", None):
            return GeneratedImage(
                image_bytes=base64.b64decode(data.b64_json),
                prompt=prompt,
                model=model_id,
            )
        if getattr(data, "url", None):
            r = httpx.get(data.url, timeout=30)
            r.raise_for_status()
            return GeneratedImage(image_bytes=r.content, prompt=prompt, model=model_id)
        raise RuntimeError(f"OpenAI không trả về ảnh. Resp: {resp}")
