"""Privacy-preserving inbound message logging."""

from __future__ import annotations

import logging

from core.phone_utils import mask_phone
from core.text_utils import sanitize_untrusted_text

logger = logging.getLogger(__name__)


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
    if log_text:
        logger.info(
            "Incoming message from %s (%s), type=%s, length=%s, text=%s",
            sender_name or "unknown",
            mask_phone(sender_id),
            message_type,
            len(incoming_text),
            sanitize_untrusted_text(incoming_text, max_text_chars) or "empty",
        )
        return

    logger.info(
        "Message from %s (%s), type=%s, length=%s",
        sender_name or "unknown",
        mask_phone(sender_id),
        message_type,
        len(incoming_text),
    )
