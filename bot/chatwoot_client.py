"""Outbound API client for Chatwoot agent-bot replies.

When the bot operates as a Chatwoot agent_bot, replies go to Chatwoot's REST
API instead of Meta's Graph API. Chatwoot then forwards the message to the
customer over WhatsApp using the same Cloud API credentials it stores.

Endpoint shape:

    POST {CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}/conversations/{conv_id}/messages
    Headers:
        api_access_token: <agent_bot_token>
        Content-Type: application/json
    Body:
        {"content": <text>, "message_type": "outgoing"}

Retry behaviour handles transient 429/5xx and network errors so user messages
are not lost on brief Chatwoot/API instability.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from core.text_utils import sanitize_untrusted_text
from settings import (
    CHATWOOT_ACCOUNT_ID,
    CHATWOOT_API_TOKEN,
    CHATWOOT_BASE_URL,
    CHATWOOT_MAX_RETRIES,
    CHATWOOT_REQUEST_TIMEOUT_SECONDS,
    CHATWOOT_RETRY_BACKOFF_SECONDS,
)

logger = logging.getLogger(__name__)

# Status codes worth retrying — transient infrastructure errors.
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
SUCCESS_STATUS_CODES = frozenset({200, 201})

# Keep jitter deterministic and tiny. This avoids retry waves without making
# tests flaky or introducing a global random dependency.
JITTER_RATIO = 0.10

__all__ = [
    "CHATWOOT_ACCOUNT_ID",
    "CHATWOOT_API_TOKEN",
    "CHATWOOT_BASE_URL",
    "CHATWOOT_MAX_RETRIES",
    "CHATWOOT_REQUEST_TIMEOUT_SECONDS",
    "CHATWOOT_RETRY_BACKOFF_SECONDS",
    "messages_url",
    "requests",
    "send_message",
    "time",
]


def messages_url(conversation_id: int | str) -> str:
    """Return the Chatwoot conversations-messages endpoint for a conversation."""
    return (
        f"{CHATWOOT_BASE_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}"
        f"/conversations/{conversation_id}/messages"
    )


def _summarize_chatwoot_error(response: requests.Response) -> str:
    """Summarize an error response without leaking message content."""
    try:
        body = response.json()
    except (AttributeError, ValueError):
        return "body omitted"

    if not isinstance(body, dict):
        return "body omitted"

    fields: list[str] = []
    for key in ("error", "message", "errors"):
        value = body.get(key)
        if not value:
            continue

        if isinstance(value, list):
            value = "; ".join(str(item) for item in value[:3])

        fields.append(f"{key}={sanitize_untrusted_text(str(value), 80)}")

    return ", ".join(fields) or "body omitted"


def _retry_delay_seconds(attempt: int) -> float:
    """Return exponential backoff delay with small deterministic jitter.

    ``attempt`` is 1-based. Attempt 1 waits roughly base seconds, attempt 2
    roughly 2x base, attempt 3 roughly 4x base, etc. The small jitter prevents
    synchronized retry waves if several requests fail at once.
    """
    base_delay: float = float(CHATWOOT_RETRY_BACKOFF_SECONDS) * float(2 ** max(0, attempt - 1))
    jitter: float = base_delay * float(JITTER_RATIO) * float((attempt % 3) + 1)
    return float(base_delay + jitter)


def _sleep_before_retry(attempt: int, max_attempts: int) -> None:
    """Sleep before the next retry using exponential backoff plus jitter."""
    if attempt >= max_attempts:
        return

    time.sleep(_retry_delay_seconds(attempt))


def _log_send_failure(
    *,
    level: int,
    message: str,
    status_code: int | None = None,
    error: str | None = None,
    attempt: int | None = None,
    max_attempts: int | None = None,
) -> None:
    """Log Chatwoot failures with consistent key/value context."""
    context: list[str] = []

    if status_code is not None:
        context.append(f"chatwoot_status={status_code}")
    if error is not None:
        context.append(f"chatwoot_error={error}")
    if attempt is not None:
        context.append(f"attempt={attempt}")
    if max_attempts is not None:
        context.append(f"max_attempts={max_attempts}")

    suffix = f" {' '.join(context)}" if context else ""
    logger.log(level, "%s%s", message, suffix)


def send_message(conversation_id: int | str, text: str) -> requests.Response | None:
    """Send a reply to a Chatwoot conversation as the agent bot.

    Returns the final response (success or last attempted failure), or None
    when configuration is missing or the request never reached the network.
    """
    if not CHATWOOT_API_TOKEN:
        logger.error("CHATWOOT_API_TOKEN is not set")
        return None

    if not CHATWOOT_ACCOUNT_ID:
        logger.error("CHATWOOT_ACCOUNT_ID is not set")
        return None

    if conversation_id in (None, "", 0, "0"):
        logger.error("Cannot send Chatwoot message: conversation_id is empty")
        return None

    if not text:
        logger.error("Cannot send Chatwoot message: text is empty")
        return None

    url = messages_url(conversation_id)
    headers = {
        "api_access_token": CHATWOOT_API_TOKEN,
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {"content": text, "message_type": "outgoing"}

    max_attempts = max(1, CHATWOOT_MAX_RETRIES)
    last_response: requests.Response | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=CHATWOOT_REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            _log_send_failure(
                level=logging.ERROR,
                message="Chatwoot send failed at network layer",
                error=exc.__class__.__name__,
                attempt=attempt,
                max_attempts=max_attempts,
            )
            _sleep_before_retry(attempt, max_attempts)
            continue

        last_response = response

        if response.status_code in SUCCESS_STATUS_CODES:
            logger.info(
                "Chatwoot reply sent conversation_id=%s chatwoot_status=%s",
                conversation_id,
                response.status_code,
            )
            return response

        if response.status_code in RETRYABLE_STATUS_CODES:
            _log_send_failure(
                level=logging.WARNING,
                message="Chatwoot send returned retryable status",
                status_code=response.status_code,
                attempt=attempt,
                max_attempts=max_attempts,
            )
            _sleep_before_retry(attempt, max_attempts)
            continue

        _log_send_failure(
            level=logging.ERROR,
            message="Chatwoot send failed",
            status_code=response.status_code,
            error=_summarize_chatwoot_error(response),
        )
        return response

    if last_response is not None:
        _log_send_failure(
            level=logging.ERROR,
            message="Chatwoot send exhausted retries",
            status_code=last_response.status_code,
            error=_summarize_chatwoot_error(last_response),
            max_attempts=max_attempts,
        )

    return last_response
