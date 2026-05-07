"""WhatsApp Cloud API client helpers."""

from __future__ import annotations

import logging
import time
from typing import Final

import requests

from core.phone_utils import is_valid_phone, mask_phone, normalize_phone
from settings import (
    GRAPH_API_VERSION,
    TEAM_NOTIFY_PHONE,
    WHATSAPP_MAX_RETRIES,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_REQUEST_TIMEOUT_SECONDS,
    WHATSAPP_RETRY_BACKOFF_SECONDS,
    WHATSAPP_TOKEN,
)
from webhook.graph_api import summarize_graph_error

logger = logging.getLogger(__name__)

RETRYABLE_WHATSAPP_STATUSES: Final = {429, 500, 502, 503, 504}


def notify_team(message: str) -> None:
    """Send an alert to the team WhatsApp number."""
    if TEAM_NOTIFY_PHONE:
        send_whatsapp_message(TEAM_NOTIFY_PHONE, message)
        logger.info("Team notified")
    else:
        logger.info("TEAM_NOTIFY_PHONE not set; team notification skipped")


def send_whatsapp_message(to_phone: str, text: str) -> requests.Response | None:
    """Send a text message through the WhatsApp Cloud API with transient retries."""
    if not WHATSAPP_TOKEN:
        logger.error("WHATSAPP_TOKEN is not set")
        return None

    if not WHATSAPP_PHONE_NUMBER_ID:
        logger.error("WHATSAPP_PHONE_NUMBER_ID is not set")
        return None

    to_phone = normalize_phone(to_phone)

    if not to_phone:
        logger.error("Cannot send message: recipient phone is empty")
        return None

    if not is_valid_phone(to_phone):
        logger.error("Cannot send message: recipient phone is invalid")
        return None

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text},
    }

    max_attempts = max(1, WHATSAPP_MAX_RETRIES)
    last_response: requests.Response | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=WHATSAPP_REQUEST_TIMEOUT_SECONDS,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            logger.warning(
                "WhatsApp send transient error: attempt=%s error=%s",
                attempt,
                exc.__class__.__name__,
            )
            _sleep_before_retry(attempt, max_attempts)
            continue
        except requests.RequestException as exc:
            logger.error("Failed to send message request: %s", exc.__class__.__name__)
            return None

        last_response = response
        if response.status_code == 200:
            logger.info("Message sent to %s", mask_phone(to_phone))
            return response

        if response.status_code not in RETRYABLE_WHATSAPP_STATUSES:
            logger.error(
                "Failed to send message: status=%s, graph_error=%s",
                response.status_code,
                summarize_graph_error(response),
            )
            return response

        logger.warning(
            "WhatsApp send retry: attempt=%s status=%s",
            attempt,
            response.status_code,
        )
        _sleep_before_retry(attempt, max_attempts)

    logger.error("WhatsApp send exhausted retries for %s", mask_phone(to_phone))
    return last_response


def _sleep_before_retry(attempt: int, max_attempts: int) -> None:
    """Sleep with exponential backoff unless there are no attempts left."""
    if attempt >= max_attempts:
        return

    time.sleep(WHATSAPP_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)))
