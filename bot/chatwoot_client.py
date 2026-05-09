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

Retry behaviour mirrors :mod:`bot.whatsapp_client` so transient 5xx and
network errors do not lose user messages.
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


def _sleep_before_retry(attempt: int, max_attempts: int) -> None:
    """Linear backoff between retries (matches whatsapp_client behaviour)."""
    if attempt >= max_attempts:
        return
    time.sleep(CHATWOOT_RETRY_BACKOFF_SECONDS * attempt)


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
            logger.error(
                "Chatwoot send attempt %s/%s failed at network layer: %s",
                attempt,
                max_attempts,
                exc.__class__.__name__,
            )
            _sleep_before_retry(attempt, max_attempts)
            continue

        last_response = response

        if response.status_code == 200 or response.status_code == 201:
            logger.info("Chatwoot reply sent to conversation %s", conversation_id)
            return response

        if response.status_code in RETRYABLE_STATUS_CODES:
            logger.warning(
                "Chatwoot send returned retryable status=%s (attempt %s/%s)",
                response.status_code,
                attempt,
                max_attempts,
            )
            _sleep_before_retry(attempt, max_attempts)
            continue

        logger.error(
            "Chatwoot send failed: status=%s, error=%s",
            response.status_code,
            _summarize_chatwoot_error(response),
        )
        return response

    if last_response is not None:
        logger.error(
            "Chatwoot send exhausted retries: status=%s, error=%s",
            last_response.status_code,
            _summarize_chatwoot_error(last_response),
        )

    return last_response
