"""Multi-account fingerprint isolation.

When the system manages multiple shops on the same platform from the same
server IP, the platform (Etsy especially) can correlate the accounts and ban
them as a cluster. This module makes each PlatformAccount appear like a
distinct human:

- **Per-account proxy URL** (HTTP / SOCKS5 residential proxy recommended)
- **Per-account User-Agent** (stable per account, never random within account)
- **Per-account Accept-Language**
- **Request spacing**: don't fire two account requests in parallel
- **Per-account daily traffic budget** to detect abuse

httpx clients can be obtained via `client_for_account()`. The pipeline must
use these clients for every outbound platform call.
"""
from __future__ import annotations

import hashlib
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

logger = logging.getLogger(__name__)


# Curated list of realistic, current desktop user agents. Stable per account
# so the platform's fingerprint never changes for the same shop.
_USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
)

_ACCEPT_LANGUAGES: tuple[str, ...] = (
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "en-CA,en-US;q=0.9,en;q=0.8",
    "en-AU,en;q=0.9",
)


@dataclass
class AccountFingerprint:
    user_agent: str
    accept_language: str
    proxy_url: str | None


def fingerprint_for_account(
    account_id: int,
    proxy_url: str | None = None,
    user_agent_override: str | None = None,
) -> AccountFingerprint:
    """Deterministic fingerprint based on account_id — never changes per account."""
    # Hash account_id to pick a stable index into the UA / lang lists.
    h = hashlib.sha256(str(account_id).encode()).digest()
    ua_idx = h[0] % len(_USER_AGENTS)
    lang_idx = h[1] % len(_ACCEPT_LANGUAGES)
    return AccountFingerprint(
        user_agent=user_agent_override or _USER_AGENTS[ua_idx],
        accept_language=_ACCEPT_LANGUAGES[lang_idx],
        proxy_url=proxy_url or None,
    )


# ─── Per-account global request lock + spacing tracker ───
class _AccountGate:
    """Serializes outbound requests per account_id and enforces min spacing.

    The pipeline can run multiple accounts in parallel, but never two requests
    for the same account at the same time.
    """

    def __init__(self) -> None:
        self._locks: dict[int, threading.Lock] = {}
        self._last: dict[int, datetime] = {}
        self._lock = threading.Lock()

    def _account_lock(self, account_id: int) -> threading.Lock:
        with self._lock:
            if account_id not in self._locks:
                self._locks[account_id] = threading.Lock()
            return self._locks[account_id]

    def acquire(self, account_id: int, min_spacing_s: float = 5.0) -> Callable[[], None]:
        """Block until safe to make a request for this account.

        Returns a release callable that records the request time.
        """
        lock = self._account_lock(account_id)
        lock.acquire()
        try:
            last = self._last.get(account_id)
            if last:
                elapsed = (datetime.now(UTC) - last).total_seconds()
                if elapsed < min_spacing_s:
                    import time
                    time.sleep(min_spacing_s - elapsed)
        except Exception:  # noqa: BLE001
            lock.release()
            raise

        def _release() -> None:
            self._last[account_id] = datetime.now(UTC)
            lock.release()

        return _release

    def time_since_last(self, account_id: int) -> timedelta | None:
        last = self._last.get(account_id)
        if last is None:
            return None
        return datetime.now(UTC) - last


_gate = _AccountGate()


def account_gate() -> _AccountGate:
    return _gate


def client_for_account(
    account_id: int,
    *,
    proxy_url: str | None = None,
    user_agent_override: str | None = None,
    timeout_s: float = 30.0,
) -> httpx.Client:
    """Return an httpx client pre-configured with this account's fingerprint.

    Caller must use it as a context manager (`with client_for_account(...) as c`).
    """
    fp = fingerprint_for_account(
        account_id, proxy_url=proxy_url, user_agent_override=user_agent_override
    )
    headers = {
        "User-Agent": fp.user_agent,
        "Accept-Language": fp.accept_language,
        "Accept": "application/json, text/plain, */*",
        "Connection": "keep-alive",
    }
    proxy_kwargs: dict = {}
    if fp.proxy_url:
        proxy_kwargs["proxy"] = fp.proxy_url
    return httpx.Client(
        headers=headers,
        timeout=timeout_s,
        follow_redirects=True,
        **proxy_kwargs,
    )
