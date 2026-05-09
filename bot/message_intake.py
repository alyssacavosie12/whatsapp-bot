"""Inbound WhatsApp message normalization and gate checks."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, Literal

from bot.message_models import IncomingMessage
from core.sender_id import mask_sender_id, parse_sender_id
from core.text_utils import sanitize_untrusted_text

logger = logging.getLogger(__name__)

MAX_SENDER_NAME_LENGTH: Final = 64
TEXT_MESSAGE_TYPE: Final = "text"

IntakeStatus = Literal[
    "duplicate",
    "invalid sender",
    "opted out",
    "rate limited",
]

SeenMessage = Callable[[str], bool]
AllowSenderMessage = Callable[[str], bool]
IsOptedOut = Callable[[str], bool]

__all__ = [
    "AllowSenderMessage",
    "IntakeResult",
    "IntakeStatus",
    "IsOptedOut",
    "MAX_SENDER_NAME_LENGTH",
    "SeenMessage",
    "TEXT_MESSAGE_TYPE",
    "intake_incoming_message",
    "sanitize_sender_name",
]


@dataclass(frozen=True)
class IntakeResult:
    """Result of validating and normalizing an inbound webhook message."""

    message: IncomingMessage | None
    status: IntakeStatus | None = None


def sanitize_sender_name(sender_name: str) -> str:
    """Return a safe customer name for logs, prompts, and team notifications."""
    return sanitize_untrusted_text(sender_name, MAX_SENDER_NAME_LENGTH)


def _extract_sender_name(value: dict[str, Any]) -> str:
    """Return the sender profile name from a webhook value object.

    The sender name is untrusted display data. It may be used in logs, prompts,
    and team notifications after sanitization, but should not drive business
    decisions or security checks.
    """
    contacts = value.get("contacts", [{}])
    if not contacts or not isinstance(contacts, list):
        return ""

    first_contact = contacts[0]
    if not isinstance(first_contact, dict):
        return ""

    profile = first_contact.get("profile", {})
    if not isinstance(profile, dict):
        return ""

    return sanitize_sender_name(str(profile.get("name", "") or ""))


def _extract_text(message: dict[str, Any], message_type: str) -> str:
    """Return normalized text body for text messages."""
    if message_type != TEXT_MESSAGE_TYPE:
        return ""

    text_payload = message.get("text", {})
    if not isinstance(text_payload, dict):
        return ""

    return str(text_payload.get("body", "") or "").strip()


def intake_incoming_message(
    value: dict[str, Any],
    message: dict[str, Any],
    *,
    seen_message: SeenMessage,
    allow_sender_message: AllowSenderMessage,
    is_opted_out: IsOptedOut,
) -> IntakeResult:
    """Validate and normalize one inbound WhatsApp webhook message."""
    message_id = str(message.get("id", "") or "")

    if message_id and seen_message(message_id):
        logger.info(
            "Duplicate message ignored: %s",
            sanitize_untrusted_text(message_id, 80),
        )
        return IntakeResult(message=None, status="duplicate")

    sender_raw = str(message.get("from", "") or "")
    sender = parse_sender_id(sender_raw)

    if sender is None:
        logger.warning(
            "Unrecognized sender id ignored: %s",
            sanitize_untrusted_text(sender_raw, 32) or "empty",
        )
        return IntakeResult(message=None, status="invalid sender")

    masked = mask_sender_id(sender)
    if is_opted_out(sender.value):
        logger.info("Opted-out sender silenced: %s", masked)
        return IntakeResult(message=None, status="opted out")

    if not allow_sender_message(sender.value):
        logger.warning("Rate limit exceeded for %s", masked)
        return IntakeResult(message=None, status="rate limited")

    message_type = str(message.get("type", "") or "")
    return IntakeResult(
        message=IncomingMessage(
            message_id=message_id,
            sender=sender,
            masked_sender=masked,
            sender_name=_extract_sender_name(value),
            message_type=message_type,
            text=_extract_text(message, message_type),
        )
    )
