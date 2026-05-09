"""Privacy-preserving inbound message logging."""

from __future__ import annotations

import logging
from typing import Final

from core.sender_id import mask_sender_id, parse_sender_id
from core.text_utils import sanitize_untrusted_text

logger = logging.getLogger(__name__)

MAX_LOG_SENDER_NAME_LENGTH: Final = 64

__all__ = [
    "MAX_LOG_SENDER_NAME_LENGTH",
    "log_incoming_text_message",
]


def _safe_sender_name(sender_name: str) -> str:
    """Return a sanitized sender display name for logs."""
    return sanitize_untrusted_text(sender_name, MAX_LOG_SENDER_NAME_LENGTH) or "unknown"


def _safe_sender_id(sender_id: str) -> str:
    """Return a privacy-preserving sender id for logs."""
    sender = parse_sender_id(sender_id)
    if sender is None:
        return "invalid"

    return mask_sender_id(sender)


def log_incoming_text_message(
    sender_name: str,
    sender_id: str,
    message_type: str,
    incoming_text: str,
    *,
    log_text: bool,
    max_text_chars: int,
) -> None:
    """Log incoming message metadata, and text only when explicitly enabled."""
    safe_name = _safe_sender_name(sender_name)
    safe_sender = _safe_sender_id(sender_id)

    if log_text:
        logger.info(
            "Incoming message from %s (%s), type=%s, length=%s, text=%s",
            safe_name,
            safe_sender,
            message_type,
            len(incoming_text),
            sanitize_untrusted_text(incoming_text, max_text_chars) or "empty",
        )
        return

    logger.info(
        "Message from %s (%s), type=%s, length=%s",
        safe_name,
        safe_sender,
        message_type,
        len(incoming_text),
    )
