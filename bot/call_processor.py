"""Orchestration for inbound WhatsApp call events."""

from __future__ import annotations

import logging
from typing import Any

from bot import whatsapp_client
from bot.content_loader import get_response
from core.sender_id import mask_sender_id, parse_sender_id
from core.text_utils import sanitize_untrusted_text
from inbox import service as inbox_service
from webhook.dedup import seen_message
from webhook.rate_limit import allow_phone_message

logger = logging.getLogger(__name__)

__all__ = ["process_call_event"]


def process_call_event(value: dict[str, Any], call: dict[str, Any]) -> str:
    """Process one WhatsApp call event from a webhook payload.

    Sends a courteous auto-reply to the caller letting them know the missed
    call was received and where to book or chat. Notifies the team if a
    notification phone is configured.
    """
    call_id = str(call.get("id", "") or "")

    if call_id and seen_message(call_id):
        logger.info(
            "Duplicate call ignored: %s",
            sanitize_untrusted_text(call_id, 80),
        )
        return "duplicate"

    caller_raw = str(call.get("from", "") or "")
    caller = parse_sender_id(caller_raw)

    if caller is None:
        logger.warning(
            "Unrecognized caller id ignored: %s",
            sanitize_untrusted_text(caller_raw, 32) or "empty",
        )
        return "invalid caller"

    caller_id = caller.value
    masked = mask_sender_id(caller)
    call_status = sanitize_untrusted_text(call.get("status", "unknown"), 32)

    logger.info("Incoming call from %s, status=%s", masked, call_status)

    if inbox_service.is_opted_out(caller_id):
        logger.info("Opted-out caller silenced: %s", masked)
        return "opted out"

    if not allow_phone_message(caller_id):
        logger.warning("Rate limit exceeded for caller %s", masked)
        return "rate limited"

    missed_call_text = get_response("missed_call", "en") or (
        "Hi! We missed your call. Please reply here to chat with us, "
        "or book online at https://www.tulumbotox.com/book."
    )

    whatsapp_client.send_whatsapp_message(caller_id, missed_call_text)
    logger.info("Missed call auto-reply sent to %s", masked)

    whatsapp_client.notify_team(
        f"MISSED CALL\nCaller: {masked}\nStatus: {call_status}\n"
        "Auto-reply sent. Follow up if needed."
    )

    return "ok"