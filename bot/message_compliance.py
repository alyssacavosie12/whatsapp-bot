"""Compliance checks and privacy-preserving inbox persistence."""

from __future__ import annotations

import logging
from collections.abc import Callable

from bot.message_models import InboxStorageResult, IncomingMessage
from bot.opt_out_keywords import is_opt_out_request as default_is_opt_out_request
from bot.sensitive_filter import (
    SENSITIVE_REDACTED_MESSAGE_TYPE,
    classify_sensitive_message,
    redacted_sensitive_body,
)

logger = logging.getLogger(__name__)

RecordOptOut = Callable[..., bool]
IsFirstContact = Callable[[str], bool]
StoreIncomingMessage = Callable[[str, str, str, str, str], None]
OptOutDetector = Callable[[str], tuple[bool, str | None, str | None]]


def record_opt_out_if_requested(
    incoming: IncomingMessage,
    *,
    record_opt_out: RecordOptOut,
    opt_out_detector: OptOutDetector = default_is_opt_out_request,
) -> bool:
    """Record text-message opt-out requests and stop further processing."""
    if not incoming.is_text:
        return False

    opted_out, opt_out_keyword, opt_out_lang = opt_out_detector(incoming.text)
    if not opted_out:
        return False

    record_opt_out(
        incoming.sender_id,
        sender_external_id_type=incoming.sender.id_type,
        source="whatsapp_keyword",
        keyword_used=opt_out_keyword or "",
        language=opt_out_lang or "",
    )
    logger.info(
        "Opt-out recorded for %s via keyword=%s",
        incoming.masked_sender,
        opt_out_keyword,
    )
    return True


def _stored_message_body(incoming: IncomingMessage) -> tuple[str, str, str | None]:
    """Return message type/body for storage and the sensitivity category.

    Sensitive messages are redacted before storage to reduce privacy risk and
    support data-minimization expectations under privacy laws such as LFPDPPP
    and GDPR-style review standards.
    """
    sensitive_category = classify_sensitive_message(incoming.text) if incoming.is_text else None
    if sensitive_category:
        return (
            SENSITIVE_REDACTED_MESSAGE_TYPE,
            redacted_sensitive_body(sensitive_category),
            sensitive_category,
        )

    return incoming.message_type, incoming.text, None


def store_incoming_for_inbox(
    incoming: IncomingMessage,
    *,
    is_first_contact: IsFirstContact,
    store_incoming_message: StoreIncomingMessage,
) -> InboxStorageResult:
    """Queue safe inbound-message persistence for the admin inbox."""
    stored_message_type, stored_body, sensitive_category = _stored_message_body(incoming)
    first_contact = is_first_contact(incoming.sender_id)

    store_incoming_message(
        incoming.message_id,
        incoming.sender_id,
        incoming.sender_name,
        stored_message_type,
        stored_body,
    )

    return InboxStorageResult(
        is_first_contact=first_contact,
        sensitive_category=sensitive_category,
    )
