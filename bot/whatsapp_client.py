"""WhatsApp Cloud API client helpers."""

from __future__ import annotations

import logging

import requests

from core.phone_utils import is_valid_phone, mask_phone, normalize_phone
from settings import (
    GRAPH_API_VERSION,
    TEAM_NOTIFY_PHONE,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_TOKEN,
)
from webhook.graph_api import summarize_graph_error

logger = logging.getLogger(__name__)


def notify_team(message: str) -> None:
    """Send an alert to the team WhatsApp number."""
    if TEAM_NOTIFY_PHONE:
        send_whatsapp_message(TEAM_NOTIFY_PHONE, message)
        logger.info("Team notified")
    else:
        logger.info("TEAM_NOTIFY_PHONE not set; team notification skipped")


def send_whatsapp_message(to_phone: str, text: str) -> requests.Response | None:
    """Send a text message through the WhatsApp Cloud API."""
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

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
    except requests.RequestException as exc:
        logger.error("Failed to send message request: %s", exc.__class__.__name__)
        return None

    if response.status_code == 200:
        logger.info("Message sent to %s", mask_phone(to_phone))
    else:
        logger.error(
            "Failed to send message: status=%s, graph_error=%s",
            response.status_code,
            summarize_graph_error(response),
        )

    return response
