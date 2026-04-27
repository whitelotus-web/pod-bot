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

    def _key(self) -> str | None:
        return self.api_key_override or settings.openai_api_key

    def generate(self, prompt: str, model: str | None = None, size: str = "1024x1024") -> GeneratedImage:
        key = self._key()
        if not key:
            raise RuntimeError("OPENAI_API_KEY chưa được cấu hình")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Cần cài openai: pip install openai") from exc

        client = OpenAI(api_key=key)
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

    def test_connection(self) -> tuple[bool, str]:
        key = self._key()
        if not key:
            return False, "Chưa có API key"
        try:
            from openai import OpenAI

            OpenAI(api_key=key).models.list()
            return True, "OK"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)[:300]
