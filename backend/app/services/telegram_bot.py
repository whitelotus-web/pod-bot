"""Telegram bot — remote control + alerts.

Two modes:

1. **Alert push** (one-way): the worker calls `send_alert(...)` from anywhere
   in the codebase to ping the user (quota exhausted, trademark hit, first
   sale, account flagged, etc.).
2. **Design approval** (interactive): in Semi-auto mode, after a design is
   generated and bg-removed, the worker calls `send_design_review(...)` which
   posts the image with inline keyboard `[✅ Duyệt & Đăng] [🔁 Sinh lại] [❌ Bỏ]`.
   The user clicks; bot writes the result to a `notifications` row that the
   worker polls.

Implemented via the Telegram Bot HTTP API directly (no python-telegram-bot
dep — keeps the worker image small). Webhook handler is in
`app/api/v1/telegram.py`.

Configuration is per-user in the `users.telegram_*` columns or environment
variables `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` for a single-user setup.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

import httpx

logger = logging.getLogger(__name__)


Severity = Literal["info", "warn", "critical"]
SEVERITY_ICON: dict[Severity, str] = {"info": "ℹ️", "warn": "⚠️", "critical": "🚨"}


@dataclass
class TelegramConfig:
    bot_token: str
    chat_id: str
    timeout_s: float = 15.0


@dataclass
class SendResult:
    success: bool
    message_id: int | None = None
    error: str = ""
    skipped: bool = False


def _api(config: TelegramConfig, method: str) -> str:
    return f"https://api.telegram.org/bot{config.bot_token}/{method}"


def send_alert(
    config: TelegramConfig | None,
    *,
    title: str,
    body: str,
    severity: Severity = "info",
) -> SendResult:
    """Plain-text notification with severity icon."""
    if config is None or not config.bot_token or not config.chat_id:
        return SendResult(success=False, skipped=True, error="no Telegram config")

    icon = SEVERITY_ICON.get(severity, "ℹ️")
    text = f"{icon} *{_md_escape(title)}*\n\n{_md_escape(body)}"[:4000]
    payload = {
        "chat_id": config.chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
    }
    try:
        with httpx.Client(timeout=config.timeout_s) as client:
            resp = client.post(_api(config, "sendMessage"), json=payload)
        if resp.status_code == 200 and resp.json().get("ok"):
            return SendResult(success=True, message_id=resp.json()["result"]["message_id"])
        return SendResult(success=False, error=f"{resp.status_code}: {resp.text[:200]}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram send failed: %s", exc)
        return SendResult(success=False, error=str(exc))


def send_design_review(
    config: TelegramConfig | None,
    *,
    image_path: str,
    caption: str,
    design_id: int,
) -> SendResult:
    """Post a design preview with inline approval keyboard."""
    if config is None or not config.bot_token or not config.chat_id:
        return SendResult(success=False, skipped=True, error="no Telegram config")

    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
    except OSError as exc:
        return SendResult(success=False, error=f"image read: {exc}")

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Duyệt & Đăng", "callback_data": f"approve:{design_id}"},
                {"text": "🔁 Sinh lại", "callback_data": f"regenerate:{design_id}"},
            ],
            [{"text": "❌ Bỏ", "callback_data": f"reject:{design_id}"}],
        ]
    }
    data = {
        "chat_id": config.chat_id,
        "caption": caption[:1024],
        "reply_markup": _json_dumps(keyboard),
    }
    files = {"photo": ("design.png", image_bytes, "image/png")}
    try:
        with httpx.Client(timeout=config.timeout_s) as client:
            resp = client.post(_api(config, "sendPhoto"), data=data, files=files)
        if resp.status_code == 200 and resp.json().get("ok"):
            return SendResult(success=True, message_id=resp.json()["result"]["message_id"])
        return SendResult(success=False, error=f"{resp.status_code}: {resp.text[:200]}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram sendPhoto failed: %s", exc)
        return SendResult(success=False, error=str(exc))


def parse_callback(callback_data: str) -> tuple[str, int] | None:
    """Parse 'approve:42' / 'regenerate:42' / 'reject:42' tuples."""
    if not callback_data or ":" not in callback_data:
        return None
    action, _, raw_id = callback_data.partition(":")
    if action not in {"approve", "regenerate", "reject"}:
        return None
    try:
        return action, int(raw_id)
    except ValueError:
        return None


# ─── helpers ───
_MD_SPECIAL = "_*[]()~`>#+-=|{}.!"


def _md_escape(s: str) -> str:
    out = []
    for ch in s or "":
        if ch in _MD_SPECIAL:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def _json_dumps(d: dict) -> str:
    import json
    return json.dumps(d, ensure_ascii=False)


def format_alert_for(kind: str, payload: dict) -> tuple[str, str, Severity]:
    """Build (title, body, severity) for a known notification kind."""
    if kind == "quota_exhausted":
        role = payload.get("role", "?")
        return (
            f"AI quota cạn cho role {role}",
            f"Tất cả key role {role} đã hết quota. {payload.get('skipped_count', 0)} design bị bỏ qua. Cần thêm key mới.",
            "critical",
        )
    if kind == "trademark_hit":
        phrase = payload.get("phrase", "?")
        return (
            f"Trademark bị chặn: {phrase}",
            f"Pipeline reject keyword/phrase '{phrase}': {payload.get('reason', '')}",
            "warn",
        )
    if kind == "first_sale":
        return (
            "Đơn hàng đầu tiên!",
            f"Listing {payload.get('listing_id', '?')} vừa có đơn đầu tiên: ${payload.get('amount', 0):.2f}",
            "info",
        )
    if kind == "account_paused":
        return (
            f"Account {payload.get('platform', '?')} bị tạm dừng",
            f"Account {payload.get('label', '?')} chuyển trạng thái paused: {payload.get('reason', '')}",
            "critical",
        )
    if kind == "design_review":
        return (
            "Cần duyệt design",
            f"Design {payload.get('design_id', '?')} đã sẵn sàng, đợi anh duyệt qua bot.",
            "info",
        )
    return ("Notification", _format_dict(payload), "info")


def _format_dict(d: Iterable | dict) -> str:
    if not isinstance(d, dict):
        return str(d)
    return "\n".join(f"{k}: {v}" for k, v in d.items())
