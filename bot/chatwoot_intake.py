"""Normalize inbound Chatwoot agent-bot message events."""

from __future__ import annotations

from typing import Any, Final

from bot.message_intake import TEXT_MESSAGE_TYPE, sanitize_sender_name
from bot.message_models import IncomingMessage
from core.sender_id import SenderId

__all__ = [
    "CHATWOOT_MEDIA_MESSAGE_TYPES",
    "build_chatwoot_incoming_message",
    "extract_chatwoot_sender_phone",
]


CHATWOOT_MEDIA_MESSAGE_TYPES: Final[tuple[str, ...]] = (
    "image",
    "document",
    "audio",
    "video",
)


def _first_string_value(source: dict[str, Any], *keys: str) -> str:
    """Return the first non-empty string value found in ``source``."""
    for key in keys:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def _sender_phone_from_conversation_meta(event: dict[str, Any]) -> str:
    """Return sender phone or identifier from conversation.meta.sender."""
    conversation = event.get("conversation", {})
    if not isinstance(conversation, dict):
        return ""

    nested = conversation.get("meta", {})
    if not isinstance(nested, dict):
        return ""

    sender = nested.get("sender", {})
    if not isinstance(sender, dict):
        return ""

    return _first_string_value(sender, "phone_number", "identifier")


def extract_chatwoot_sender_phone(event: dict[str, Any]) -> str:
    """Pull the customer's phone number or identifier from a Chatwoot event.

    Chatwoot may expose the contact in several places depending on inbox type
    and webhook shape. Prefer the direct sender object, then conversation
    metadata, then contact-level fallbacks.
    """
    candidate = ""

    direct_sender = event.get("sender", {})
    if isinstance(direct_sender, dict):
        candidate = _first_string_value(
            direct_sender,
            "phone_number",
            "identifier",
        )

    if not candidate:
        candidate = _sender_phone_from_conversation_meta(event)

    if not candidate:
        contact = event.get("contact", {})
        if isinstance(contact, dict):
            candidate = _first_string_value(
                contact,
                "phone_number",
                "identifier",
            )

    if not candidate:
        contact_inbox = event.get("contact_inbox", {})
        if isinstance(contact_inbox, dict):
            candidate = _first_string_value(contact_inbox, "source_id")

    if candidate.startswith("+"):
        candidate = candidate[1:]

    return candidate


def _chatwoot_message_type(content_type: str, is_text: bool) -> str:
    """Map Chatwoot content_type to the bot's message_type vocabulary."""
    if is_text:
        return TEXT_MESSAGE_TYPE

    normalized = content_type.lower()
    for message_type in CHATWOOT_MEDIA_MESSAGE_TYPES:
        if message_type in normalized:
            return message_type

    # Unknown non-text Chatwoot payloads should still receive the generic
    # media response handled by bot.message_responses.
    return "image"


def _chatwoot_sender_name(event: dict[str, Any]) -> str:
    """Return a sanitized customer display name from the Chatwoot event."""
    sender_data = event.get("sender", {})
    if isinstance(sender_data, dict):
        raw_sender_name = sender_data.get("name", "")
        return sanitize_sender_name(str(raw_sender_name or ""))

    return ""


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
