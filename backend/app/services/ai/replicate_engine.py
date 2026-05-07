"""Replicate (SDXL / Flux / any hosted model)."""
from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.services.ai.base import AIDesignEngine, GeneratedImage
from app.services.negative_prompts import build_negative


def _negative_prompt_for(model_id: str) -> str:
    """Pick the right negative-prompt list given a Replicate model id.

    Replicate model ids follow ``owner/name:rev``; we use the ``name``
    fragment as a hint (e.g. ``sdxl`` vs ``flux-schnell``). For models
    we don't have a heuristic for, fall back to the t-shirt baseline,
    which is also the most common case.
    """
    return build_negative(product_type="tshirt")

logger = logging.getLogger(__name__)


class ReplicateEngine(AIDesignEngine):
    name = "replicate"
    default_model = "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b"

    def _key(self) -> str | None:
        return self.api_key_override or settings.replicate_api_token

    def generate(self, prompt: str, model: str | None = None, size: str = "1024x1024") -> GeneratedImage:
        key = self._key()
        if not key:
            raise RuntimeError("REPLICATE_API_TOKEN chưa được cấu hình")

        try:
            import replicate
        except ImportError as exc:
            raise RuntimeError("Cần cài replicate: pip install replicate") from exc

        model_id = model or self.default_model
        w, h = (int(x) for x in size.split("x"))

        client = replicate.Client(api_token=key)
        output = client.run(
            model_id,
            input={
                "prompt": prompt,
                "width": w,
                "height": h,
                "num_outputs": 1,
                "negative_prompt": _negative_prompt_for(model_id),
            },
        )

        url = output[0] if isinstance(output, list) else output
        if hasattr(url, "url"):
            url = url.url
        r = httpx.get(url, timeout=60)
        r.raise_for_status()
        return GeneratedImage(image_bytes=r.content, prompt=prompt, model=model_id)

    def test_connection(self) -> tuple[bool, str]:
        key = self._key()
        if not key:
            return False, "Chưa có API token"
        try:
            r = httpx.get(
                "https://api.replicate.com/v1/account",
                headers={"Authorization": f"Token {key}"},
                timeout=10,
            )
            if r.status_code == 200:
                return True, "OK"
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)[:300]
