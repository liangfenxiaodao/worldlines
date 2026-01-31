"""Telegram Bot API client — send messages via bot token."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"


@dataclass(frozen=True)
class SendResult:
    """Result of a Telegram sendMessage call."""

    ok: bool
    message_id: int | None = None
    error: str | None = None


def send_message(
    bot_token: str,
    chat_id: str,
    text: str,
    *,
    parse_mode: str = "HTML",
    max_retries: int = 3,
) -> SendResult:
    """Send a single message via the Telegram Bot API.

    Uses exponential backoff on failure: 2^attempt seconds (1s, 2s, 4s, ...).
    Returns a structured result — never raises.
    """
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }

    last_error = ""
    for attempt in range(max_retries):
        try:
            response = httpx.post(url, json=payload, timeout=30)
            data = response.json()
            if data.get("ok"):
                msg_id = data["result"]["message_id"]
                logger.info("Telegram message sent: message_id=%d", msg_id)
                return SendResult(ok=True, message_id=msg_id)
            last_error = data.get("description", "Unknown Telegram error")
            logger.warning(
                "Telegram API error (attempt %d/%d): %s",
                attempt + 1, max_retries, last_error,
            )
        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "Telegram request failed (attempt %d/%d): %s",
                attempt + 1, max_retries, last_error,
            )

        if attempt < max_retries - 1:
            backoff = 2 ** attempt
            time.sleep(backoff)

    return SendResult(ok=False, error=last_error)


def send_messages(
    bot_token: str,
    chat_id: str,
    chunks: list[str],
    *,
    parse_mode: str = "HTML",
    max_retries: int = 3,
) -> list[SendResult]:
    """Send multiple message chunks in order. Stops on first failure."""
    results: list[SendResult] = []
    for chunk in chunks:
        result = send_message(
            bot_token, chat_id, chunk, parse_mode=parse_mode, max_retries=max_retries,
        )
        results.append(result)
        if not result.ok:
            break
    return results
