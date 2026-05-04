"""Auto customer care for Etsy.

Two flows:

1. **Auto-reply**: classifies an incoming Etsy buyer message and emits a
   templated reply. We try AI classification first (Gemini text role), fall
   back to regex/keyword classification when no AI key is configured.
2. **Auto review request**: 2 days after a Printify order is marked
   "delivered", build a polite multilingual review request that the worker
   sends via the Etsy Conversations API.

This module is **pure logic** — no HTTP. The actual Etsy API call lives in
`app/services/platforms/etsy_messages.py` (consumed by the worker).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)


Intent = Literal[
    "shipping_status",
    "size_question",
    "refund_return",
    "complaint",
    "compliment",
    "custom_request",
    "other",
]


@dataclass
class ClassifiedMessage:
    intent: Intent
    confidence: float  # 0..1
    reply: str
    needs_human: bool = False


# Keyword heuristics — used when AI is unavailable, AND as the AI prompt's
# anchor list so output is constrained.
_INTENT_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    "shipping_status": (
        "where is", "where's my", "tracking", "ship", "shipping",
        "delivery", "delivered", "arrive", "still waiting", "package",
    ),
    "size_question": (
        "size", "fit", "small", "medium", "large", "xl", "measurement",
        "dimensions", "what size",
    ),
    "refund_return": (
        "refund", "return", "exchange", "money back", "wrong item",
        "damaged", "defective",
    ),
    "complaint": (
        "terrible", "horrible", "worst", "scam", "fraud", "complaint",
        "lawyer", "report", "ftc", "bbb",
    ),
    "compliment": (
        "love", "amazing", "beautiful", "perfect", "thank you", "thanks",
        "best", "great", "wonderful", "excellent",
    ),
    "custom_request": (
        "custom", "personalize", "personalise", "different color",
        "change the", "can you make", "modify",
    ),
}


def _classify_keywords(message: str) -> tuple[Intent, float]:
    text = message.lower()
    best: Intent = "other"
    best_score = 0
    for intent, keywords in _INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best = intent
    confidence = min(1.0, 0.4 + 0.2 * best_score)
    if best_score == 0:
        confidence = 0.3
    return best, confidence


_AI_CLASSIFY_PROMPT = """Classify this Etsy buyer message into ONE category.

Message: {message}

Categories:
- shipping_status: asking about delivery / tracking
- size_question: asking about size, fit, measurements
- refund_return: requesting refund, return, exchange
- complaint: angry, threatening, escalation
- compliment: positive feedback, thanks
- custom_request: asking for personalization or customization
- other: anything else

Output STRICT JSON: {{"intent": "<category>", "confidence": <0..1>}}
"""


def classify_message(
    message: str,
    *,
    ai_caller=None,  # callable: (prompt: str) -> str
) -> tuple[Intent, float]:
    """Try AI first, fall back to keyword heuristic."""
    if ai_caller is not None:
        try:
            raw = ai_caller(_AI_CLASSIFY_PROMPT.format(message=message[:1000]))
            text = re.sub(r"^```json\s*|\s*```$", "", (raw or "").strip())
            data = json.loads(text)
            intent = data.get("intent", "other")
            if intent in {
                "shipping_status", "size_question", "refund_return",
                "complaint", "compliment", "custom_request", "other",
            }:
                return intent, float(data.get("confidence", 0.6))  # type: ignore[return-value]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Auto-CS AI classify failed: %s", exc)
    return _classify_keywords(message)


# Reply templates indexed by intent. Variables: {tracking_url}, {buyer_name},
# {est_delivery}, {return_policy_url}, {size_chart_url}, {shop_name}.
REPLY_TEMPLATES: dict[Intent, str] = {
    "shipping_status": (
        "Hi {buyer_name},\n\n"
        "Thanks so much for reaching out! Your order is on its way. "
        "You can follow tracking here: {tracking_url}\n"
        "Estimated delivery: {est_delivery}.\n\n"
        "If you don't see updates within 48 hours, please reply and we'll dig in. "
        "Thanks for your patience!\n\n"
        "— {shop_name}"
    ),
    "size_question": (
        "Hi {buyer_name},\n\n"
        "Great question! Our size chart is here: {size_chart_url}\n\n"
        "If you're between sizes, we generally recommend going up one size for a "
        "relaxed fit. Let me know which size you're considering and I can give "
        "more specific advice.\n\n"
        "— {shop_name}"
    ),
    "refund_return": (
        "Hi {buyer_name},\n\n"
        "I'm sorry the order didn't work out — we want to make this right. "
        "You can find our full return policy here: {return_policy_url}\n\n"
        "If the item arrived damaged or different from the listing, please reply "
        "with a photo and we'll process a refund or replacement right away.\n\n"
        "— {shop_name}"
    ),
    "complaint": (
        "Hi {buyer_name},\n\n"
        "I hear you and I'm really sorry. I'm escalating this to a human teammate "
        "who will follow up within 24 hours.\n\n"
        "— {shop_name}"
    ),
    "compliment": (
        "Hi {buyer_name},\n\n"
        "Thank you so much for the kind words! It truly makes our day. If you "
        "feel like leaving a review on the listing, that helps tiny shops like "
        "ours a ton. ❤️\n\n"
        "— {shop_name}"
    ),
    "custom_request": (
        "Hi {buyer_name},\n\n"
        "Thanks for asking! Custom orders are something we sometimes do — I'm "
        "passing this to a teammate who'll review and get back to you with "
        "options + pricing within 24 hours.\n\n"
        "— {shop_name}"
    ),
    "other": (
        "Hi {buyer_name},\n\n"
        "Thanks for reaching out — a teammate will get back to you within "
        "24 hours.\n\n"
        "— {shop_name}"
    ),
}


def render_reply(
    intent: Intent,
    *,
    buyer_name: str = "there",
    tracking_url: str = "",
    est_delivery: str = "",
    size_chart_url: str = "",
    return_policy_url: str = "",
    shop_name: str = "your shop",
) -> str:
    return REPLY_TEMPLATES[intent].format(
        buyer_name=buyer_name or "there",
        tracking_url=tracking_url or "(coming shortly)",
        est_delivery=est_delivery or "5-10 business days",
        size_chart_url=size_chart_url or "https://www.etsy.com",
        return_policy_url=return_policy_url or "https://www.etsy.com",
        shop_name=shop_name or "your shop",
    )


def auto_handle(
    message: str,
    *,
    buyer_name: str = "",
    tracking_url: str = "",
    est_delivery: str = "",
    shop_name: str = "",
    ai_caller=None,
) -> ClassifiedMessage:
    intent, confidence = classify_message(message, ai_caller=ai_caller)
    reply = render_reply(
        intent,
        buyer_name=buyer_name,
        tracking_url=tracking_url,
        est_delivery=est_delivery,
        shop_name=shop_name,
    )
    needs_human = intent in {"complaint", "custom_request", "refund_return"} or confidence < 0.5
    return ClassifiedMessage(
        intent=intent,
        confidence=confidence,
        reply=reply,
        needs_human=needs_human,
    )


# ─── Review request ───
REVIEW_REQUEST_TEMPLATE = (
    "Hi {buyer_name},\n\n"
    "Thank you so much for your purchase from {shop_name}! "
    "I hope your {item_label} arrived in great shape and that you're loving it. "
    "If you have a moment, a quick review on Etsy would mean the world — small "
    "shops like ours rely on them so much.\n\n"
    "If anything wasn't perfect, just reply to this message and we'll fix it right "
    "away.\n\n"
    "Thanks again,\n{shop_name}"
)


def render_review_request(
    *,
    buyer_name: str = "",
    shop_name: str = "your shop",
    item_label: str = "order",
) -> str:
    return REVIEW_REQUEST_TEMPLATE.format(
        buyer_name=buyer_name or "there",
        shop_name=shop_name,
        item_label=item_label,
    )
