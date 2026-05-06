"""Tests for Wave 6 / 7 / 8 / 9 / 10 additions."""
from __future__ import annotations

import io

import pytest


def test_etsy_fees_basic():
    from app.services.etsy_fees import fees_for_order

    f = fees_for_order(item_price_usd=20.0, listing_renewal_due=True)
    expected = 0.20 + 0.065 * 20 + 0.03 * 20 + 0.25
    assert abs(f.total - expected) < 1e-6
    assert f.listing_fee > 0
    assert f.transaction_fee > 0
    assert f.payment_fee > 0

    # Without renewal trigger, listing fee is excluded.
    f2 = fees_for_order(item_price_usd=20.0)
    assert f2.listing_fee == 0.0


def test_negative_prompt_composition():
    from app.services.negative_prompts import (
        build_negative,
        supported_product_types,
    )

    base = build_negative(product_type="tshirt")
    assert "watermark" in base
    assert "background" in base  # tshirt-specific

    wall = build_negative(product_type="wall_art")
    assert "frame" in wall
    assert "background" not in wall  # wall_art does NOT exclude background

    extra = build_negative(product_type="tshirt", extra=["disney style", "watermark"])
    # Dedupe on lowercase comparison
    assert extra.lower().count("watermark") == 1
    assert "disney style" in extra

    assert "tshirt" in supported_product_types()


def test_trend_predictor_rising_vs_declining():
    from app.services.trend_predictor import predict, score_for_scout

    rising = [10, 11, 13, 16, 21, 28, 36, 48, 60, 75]
    f = predict(rising)
    assert f.direction == "rising"
    assert f.slope_per_day > 0
    assert score_for_scout(rising) > 1.0

    declining = list(reversed(rising))
    f2 = predict(declining)
    assert f2.direction == "declining"
    assert score_for_scout(declining) < 1.0

    flat = [50] * 10
    f3 = predict(flat)
    assert f3.direction == "stable"


def test_trend_predictor_handles_short_series():
    from app.services.trend_predictor import predict

    f = predict([1, 2])
    assert f.direction == "unknown"
    assert f.next_7d_estimate is None


def test_style_consistency_self_distance_zero():
    pytest.importorskip("PIL")
    from PIL import Image

    from app.services.style_consistency import (
        compute_signature,
        distance,
        is_consistent,
    )

    buf = io.BytesIO()
    Image.new("RGB", (256, 256), (10, 80, 200)).save(buf, format="PNG")
    sig = compute_signature(buf.getvalue())
    assert sig is not None

    d = distance(sig, sig)
    assert d < 1e-6

    consistent, score = is_consistent(sig, [sig, sig, sig])
    assert consistent is True
    assert score < 0.05


def test_style_consistency_different_images():
    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw

    from app.services.style_consistency import compute_signature, distance

    buf_a = io.BytesIO()
    Image.new("RGB", (256, 256), (10, 80, 200)).save(buf_a, format="PNG")

    buf_b = io.BytesIO()
    img_b = Image.new("RGB", (256, 256), (255, 255, 255))
    draw = ImageDraw.Draw(img_b)
    draw.rectangle([(0, 0), (256, 128)], fill=(255, 0, 0))
    draw.rectangle([(0, 128), (256, 256)], fill=(0, 0, 0))
    img_b.save(buf_b, format="PNG")

    sa = compute_signature(buf_a.getvalue())
    sb = compute_signature(buf_b.getvalue())
    assert sa is not None and sb is not None
    assert distance(sa, sb) > 0.3


def test_webhook_signing_etsy_dev_mode():
    import os

    os.environ.pop("ETSY_WEBHOOK_SECRET", None)
    os.environ["ENVIRONMENT"] = "development"

    from app.core.webhook_signing import verify_etsy_webhook

    # In dev mode without a secret, we accept (but log a warning).
    assert verify_etsy_webhook(b"hello", None) is True


def test_webhook_signing_with_secret():
    import hashlib
    import hmac
    import os

    os.environ["ETSY_WEBHOOK_SECRET"] = "topsecret"
    body = b'{"order_id": 1}'
    sig = hmac.new(b"topsecret", body, hashlib.sha256).hexdigest()

    from app.core.webhook_signing import verify_etsy_webhook

    assert verify_etsy_webhook(body, sig) is True
    assert verify_etsy_webhook(body, "sha256=" + sig) is True
    assert verify_etsy_webhook(body, "deadbeef") is False
    assert verify_etsy_webhook(body, None) is False

    os.environ.pop("ETSY_WEBHOOK_SECRET", None)


def test_totp_roundtrip():
    from app.services.totp import generate_secret, provisioning_uri, verify

    s = generate_secret()
    assert len(s) >= 16

    uri = provisioning_uri(secret_b32=s, label="user@podbot.io")
    assert uri.startswith("otpauth://totp/")
    assert "secret=" in uri

    # Compute current valid code via the same algorithm and verify it.
    import base64
    import hmac
    import struct
    import time

    pad = "=" * ((8 - len(s) % 8) % 8)
    key = base64.b32decode(s + pad)
    counter = int(time.time()) // 30
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, "sha1").digest()
    o = h[-1] & 0x0F
    code = (
        ((h[o] & 0x7F) << 24)
        | ((h[o + 1] & 0xFF) << 16)
        | ((h[o + 2] & 0xFF) << 8)
        | (h[o + 3] & 0xFF)
    ) % 10**6
    code_str = f"{code:06d}"
    assert verify(s, code_str) is True
    assert verify(s, "000000") in (False, True)  # may or may not match
    assert verify(s, "abc") is False  # non-digits rejected


def test_platform_registry_includes_new_platforms():
    from app.services.platforms.base import PLATFORM_META, get_platform

    for name in ("gelato", "redbubble", "society6", "amazon_merch", "spreadshirt"):
        assert name in PLATFORM_META

    with pytest.raises(ValueError):
        get_platform("nonexistent_platform", account=None)
