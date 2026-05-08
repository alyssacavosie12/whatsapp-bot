"""Normalize inbound Chatwoot agent-bot message events."""

from __future__ import annotations

from typing import Any

from bot.message_intake import TEXT_MESSAGE_TYPE, sanitize_sender_name
from bot.message_models import IncomingMessage
from core.sender_id import SenderId

__all__ = [
    "build_chatwoot_incoming_message",
    "extract_chatwoot_sender_phone",
]


def extract_chatwoot_sender_phone(event: dict[str, Any]) -> str:
    """Pull the customer's phone number or identifier from a Chatwoot event.

    Chatwoot may expose the contact under ``sender`` or under
    ``conversation.meta.sender``. We try both.
    """
    candidate = ""

    direct_sender = event.get("sender", {})
    if isinstance(direct_sender, dict):
        phone = direct_sender.get("phone_number") or direct_sender.get("identifier")
        if isinstance(phone, str) and phone:
            candidate = phone

    if not candidate:
        conversation = event.get("conversation", {})
        if isinstance(conversation, dict):
            nested = conversation.get("meta", {})
            if isinstance(nested, dict):
                sender = nested.get("sender", {})
                if isinstance(sender, dict):
                    phone = sender.get("phone_number") or sender.get("identifier")
                    if isinstance(phone, str) and phone:
                        candidate = phone

    candidate = candidate.strip()
    if candidate.startswith("+"):
        candidate = candidate[1:]

    return candidate


def _chatwoot_message_type(content_type: str, is_text: bool) -> str:
    """Map Chatwoot content_type to the bot's message_type vocabulary."""
    if is_text:
        return TEXT_MESSAGE_TYPE

    normalized = content_type.lower()
    for message_type in ("image", "document", "audio", "video"):
        if message_type in normalized:
            return message_type

    # Unknown non-text Chatwoot payloads should still receive the generic
    # media response handled by bot.message_responses.
    return "image"


def _chatwoot_sender_name(event: dict[str, Any]) -> str:
    sender_data = event.get("sender", {})
    raw_sender_name = (
        sender_data.get("name", "") if isinstance(sender_data, dict) else ""
    )
    return sanitize_sender_name(raw_sender_name)


def build_chatwoot_incoming_message(
    event: dict[str, Any],
    *,
    sender: SenderId,
    masked_sender: str,
) -> IncomingMessage:
    """Build a normalized IncomingMessage from a Chatwoot event."""
    message_id = str(event.get("id", "") or "")
    incoming_text = str(event.get("content", "") or "").strip()
    content_type = str(event.get("content_type", "") or "")
    is_text = bool(incoming_text) and content_type in ("", "text")

    return IncomingMessage(
        message_id=message_id,
        sender=sender,
        masked_sender=masked_sender,
        sender_name=_chatwoot_sender_name(event),
        message_type=_chatwoot_message_type(content_type, is_text),
        text=incoming_text if is_text else "",
    )