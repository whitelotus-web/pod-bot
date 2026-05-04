"""Tests for Wave 3: telegram bot, customer care, branding, health monitor."""
from __future__ import annotations

# ─── Telegram bot ───


def test_telegram_skipped_when_no_config():
    from app.services.telegram_bot import send_alert

    result = send_alert(None, title="x", body="y")
    assert result.skipped
    assert not result.success


def test_telegram_md_escape():
    from app.services.telegram_bot import _md_escape

    out = _md_escape("Hello *world*!")
    # Both * and ! must be escaped.
    assert "\\*" in out
    assert "\\!" in out


def test_telegram_parse_callback():
    from app.services.telegram_bot import parse_callback

    assert parse_callback("approve:42") == ("approve", 42)
    assert parse_callback("regenerate:99") == ("regenerate", 99)
    assert parse_callback("reject:1") == ("reject", 1)
    assert parse_callback("foo:bar") is None
    assert parse_callback("") is None
    assert parse_callback("approve:abc") is None


def test_telegram_format_alert_known_kinds():
    from app.services.telegram_bot import format_alert_for

    title, _body, sev = format_alert_for("quota_exhausted", {"role": "image_generation", "skipped_count": 3})
    assert "image_generation" in title
    assert sev == "critical"

    title, _body, sev = format_alert_for("first_sale", {"listing_id": 100, "amount": 24.99})
    assert sev == "info"

    title, _body, sev = format_alert_for("trademark_hit", {"phrase": "Disney"})
    assert "Disney" in title
    assert sev == "warn"


# ─── Customer care ───


def test_cs_classify_shipping_question():
    from app.services.customer_care import classify_message

    intent, conf = classify_message("Hi, where is my package? I haven't seen tracking yet")
    assert intent == "shipping_status"
    assert conf > 0.4


def test_cs_classify_size_question():
    from app.services.customer_care import classify_message

    intent, _conf = classify_message("Do you have this in size XL?")
    assert intent == "size_question"


def test_cs_classify_complaint_keywords():
    from app.services.customer_care import classify_message

    intent, _conf = classify_message("This is the worst! I'm reporting you to the BBB")
    assert intent == "complaint"


def test_cs_render_shipping_reply_substitutes():
    from app.services.customer_care import render_reply

    out = render_reply(
        "shipping_status",
        buyer_name="Alex",
        tracking_url="https://t/123",
        est_delivery="June 5",
        shop_name="Star Studio",
    )
    assert "Alex" in out
    assert "https://t/123" in out
    assert "Star Studio" in out


def test_cs_auto_handle_complaint_needs_human():
    from app.services.customer_care import auto_handle

    res = auto_handle(
        "Terrible experience, this is fraud!",
        buyer_name="Pat",
        shop_name="My Shop",
    )
    assert res.intent == "complaint"
    assert res.needs_human is True


def test_cs_auto_handle_compliment_no_human():
    from app.services.customer_care import auto_handle

    res = auto_handle(
        "I LOVE this shirt, thank you so much!!",
        buyer_name="Sam",
    )
    assert res.intent == "compliment"
    assert res.needs_human is False


def test_cs_render_review_request():
    from app.services.customer_care import render_review_request

    out = render_review_request(
        buyer_name="Jordan",
        shop_name="Cozy Studio",
        item_label="Halloween mug",
    )
    assert "Jordan" in out
    assert "Cozy Studio" in out
    assert "Halloween mug" in out


def test_cs_ai_caller_path_uses_returned_intent():
    from app.services.customer_care import classify_message

    def fake_ai(_p: str) -> str:
        return '{"intent": "custom_request", "confidence": 0.85}'

    intent, conf = classify_message("hello", ai_caller=fake_ai)
    assert intent == "custom_request"
    assert conf == 0.85


def test_cs_ai_invalid_falls_back():
    from app.services.customer_care import classify_message

    def bad_ai(_p: str) -> str:
        return "this isn't json"

    # Falls back to keyword classifier; "size" present → size_question.
    intent, _conf = classify_message("what size should I order?", ai_caller=bad_ai)
    assert intent == "size_question"


# ─── Shop branding ───


def test_branding_template_pack_complete():
    from app.services.shop_branding import generate

    pack = generate("vintage cat lovers")
    assert pack.source == "template"
    assert pack.banner_prompt
    assert pack.logo_prompt
    assert len(pack.about_section) >= 400
    assert pack.policies
    assert 4 <= len(pack.shop_sections) <= 6
    assert any("vintage cat lovers".lower() in s.lower() for s in pack.shop_sections)


def test_branding_ai_path():
    from app.services.shop_branding import generate

    def fake_ai(_p: str) -> str:
        return (
            '{"banner_prompt": "banner here",'
            ' "logo_prompt": "logo here",'
            ' "about_section": "' + ("about " * 100) + '",'
            ' "announcement": "weekly drop!",'
            ' "policies": "**Shipping**\\n3-5 days",'
            ' "shop_sections": ["Apparel", "Accessories", "Gifts", "New"]}'
        )

    pack = generate("hiking", ai_caller=fake_ai)
    assert pack.source == "ai"
    assert pack.banner_prompt == "banner here"
    assert len(pack.shop_sections) == 4


def test_branding_ai_thin_falls_back():
    from app.services.shop_branding import generate

    def thin_ai(_p: str) -> str:
        return '{"banner_prompt": "x", "about_section": "too short"}'

    pack = generate("hiking", ai_caller=thin_ai)
    assert pack.source == "template"  # validation fell through


# ─── Account health ───


def test_health_evaluate_default_healthy():
    from app.services.account_health import HealthInputs, evaluate

    decision = evaluate(HealthInputs())
    assert decision.status == "healthy"


def test_health_pauses_on_explicit_review_flag():
    from app.services.account_health import HealthInputs, evaluate

    decision = evaluate(HealthInputs(explicit_review_flag=True))
    assert decision.status == "paused"
    assert decision.paused_until is not None


def test_health_pauses_on_many_429s():
    from app.services.account_health import HealthInputs, evaluate

    decision = evaluate(HealthInputs(recent_429s=6))
    assert decision.status == "paused"


def test_health_warn_on_elevated_error_rate():
    from app.services.account_health import HealthInputs, evaluate

    decision = evaluate(HealthInputs(recent_errors=2, recent_publish_attempts=8))
    assert decision.status == "warn"


def test_health_pause_on_majority_failures():
    from app.services.account_health import HealthInputs, evaluate

    decision = evaluate(HealthInputs(recent_errors=4, recent_publish_attempts=6))
    assert decision.status == "paused"


def test_health_link_correlation():
    from app.services.account_health import link_correlation_signal

    # Two accounts erroring → linkage signal
    assert link_correlation_signal([(1, 3), (2, 2), (3, 0)]) is True
    # Single account erroring is not linkage
    assert link_correlation_signal([(1, 5), (2, 0), (3, 0)]) is False
