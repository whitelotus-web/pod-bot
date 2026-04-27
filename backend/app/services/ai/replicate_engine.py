"""Replicate (SDXL / Flux / any hosted model)."""
from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.services.ai.base import AIDesignEngine, GeneratedImage

logger = logging.getLogger(__name__)


class ReplicateEngine(AIDesignEngine):
    name = "replicate"
    default_model = "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b"

    def generate(self, prompt: str, model: str | None = None, size: str = "1024x1024") -> GeneratedImage:
        if not settings.replicate_api_token:
            raise RuntimeError("REPLICATE_API_TOKEN chưa được cấu hình")

        try:
            import replicate
        except ImportError as exc:
            raise RuntimeError("Cần cài replicate: pip install replicate") from exc

        model_id = model or self.default_model
        w, h = (int(x) for x in size.split("x"))

        client = replicate.Client(api_token=settings.replicate_api_token)
        output = client.run(
            model_id,
            input={
                "prompt": prompt,
                "width": w,
                "height": h,
                "num_outputs": 1,
                "negative_prompt": "watermark, text, logo, low quality, blurry",
            },
        )

        url = output[0] if isinstance(output, list) else output
        if hasattr(url, "url"):
            url = url.url
        r = httpx.get(url, timeout=60)
        r.raise_for_status()
        return GeneratedImage(image_bytes=r.content, prompt=prompt, model=model_id)
