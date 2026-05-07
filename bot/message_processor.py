"""Processing for one inbound WhatsApp message."""

from __future__ import annotations

import logging
from typing import Any, Final

from bot import whatsapp_client
from bot.ai_responder import get_ai_response
from bot.content_loader import detect_language, get_response
from bot.faq import find_best_faq_match
from bot.opt_out_keywords import is_opt_out_request
from core.phone_utils import mask_phone
from core.sender_id import mask_sender_id, parse_sender_id
from core.text_utils import sanitize_untrusted_text
from inbox import service as inbox_service
from settings import (
    BOT_DISCLOSURE,
    INCOMING_MESSAGE_LOG_MAX_CHARS,
    LOG_INCOMING_MESSAGES,
    MAX_INCOMING_TEXT_CHARS,
)
from webhook.dedup import seen_message
from webhook.rate_limit import allow_phone_message

logger = logging.getLogger(__name__)

TEXT_MESSAGE_TYPE: Final = "text"
HUMAN_HANDOFF_KEYWORD: Final = "HUMAN"
MEDIA_MESSAGE_TYPES: Final = {"image", "document", "audio", "video"}
MAX_SENDER_NAME_LENGTH: Final = 64
MESSAGE_TOO_LONG_FALLBACK: Final[dict[str, str]] = {
    "en": "Thanks - that message is too long. Please send a shorter version.",
    "es": "Gracias - ese mensaje es demasiado largo. Envia una version mas corta.",
}
OPT_OUT_CONFIRMATION_FALLBACK: Final[dict[str, str]] = {
    "en": (
        "You've been unsubscribed. You will not receive further automated "
        "messages from Tulum BTX. To re-enable, contact us at tulumbotox.com."
    ),
    "es": (
        "Has cancelado la suscripcion. No recibiras mas mensajes automaticos "
        "de Tulum BTX. Para reactivar, contactanos en tulumbotox.com."
    ),
}


def sanitize_sender_name(sender_name: str) -> str:
    """Return a safe customer name for logs, prompts, and team notifications."""
    return sanitize_untrusted_text(sender_name, MAX_SENDER_NAME_LENGTH)


def get_message_too_long_response(lang: str) -> str:
    """Return configured or built-in response for overlong customer messages."""
    return get_response("message_too_long", lang) or MESSAGE_TOO_LONG_FALLBACK[lang]


def get_opt_out_confirmation_response(lang: str) -> str:
    """Return configured or built-in confirmation for an opt-out request."""
    return get_response("opt_out_confirmation", lang) or OPT_OUT_CONFIRMATION_FALLBACK[lang]


def build_handoff_notification(sender_name: str, sender: object) -> str:
    """Build a safe team alert for human handoff requests.

    Accepts a `SenderId` (preferred) or a raw phone string. BSUID senders
    can't be paged on a phone, so the line is labeled accordingly.
    """
    from core.sender_id import SenderId

    safe_name = sanitize_sender_name(sender_name) or "unknown"

    if isinstance(sender, SenderId):
        if sender.is_phone:
            return (
                "HUMAN REQUESTED\n"
                f"Customer name: {safe_name}\n"
                f"Customer phone: +{sender.value}\n"
                "Please respond to them directly."
            )
        return (
            "HUMAN REQUESTED\n"
            f"Customer name: {safe_name}\n"
            f"Customer id (BSUID): {sender.value}\n"
            "Phone is hidden by Meta; reply via WhatsApp Business inbox."
        )

    # Backward-compat: raw phone string passthrough.
    parsed = parse_sender_id(str(sender or ""))
    safe_phone = parsed.value if parsed and parsed.is_phone else "invalid"
    return (
        "HUMAN REQUESTED\n"
        f"Customer name: {safe_name}\n"
        f"Customer phone: +{safe_phone}\n"
        "Please respond to them directly."
    )


def log_incoming_text_message(
    sender_name: str,
    sender_id: str,
    message_type: str,
    incoming_text: str,
) -> None:
    """Log incoming message metadata, and text only when explicitly enabled."""
    if LOG_INCOMING_MESSAGES:
        logger.info(
            "Incoming message from %s (%s), type=%s, length=%s, text=%s",
            sender_name or "unknown",
            mask_phone(sender_id),
            message_type,
            len(incoming_text),
            sanitize_untrusted_text(incoming_text, INCOMING_MESSAGE_LOG_MAX_CHARS) or "empty",
        )
        return

    logger.info(
        "Message from %s (%s), type=%s, length=%s",
        sender_name or "unknown",
        mask_phone(sender_id),
        message_type,
        len(incoming_text),
    )


def process_webhook_message(value: dict[str, Any], message: dict[str, Any]) -> str:
    """Process one WhatsApp message from a webhook payload."""
    message_id = message.get("id", "")

    if message_id and seen_message(message_id):
        logger.info(
            "Duplicate message ignored: %s",
            sanitize_untrusted_text(message_id, 80),
        )
        return "duplicate"

    sender_raw = message.get("from", "")
    sender = parse_sender_id(sender_raw)

    if sender is None:
        logger.warning(
            "Unrecognized sender id ignored: %s",
            sanitize_untrusted_text(sender_raw, 32) or "empty",
        )
        return "invalid sender"

    sender_id = sender.value
    masked = mask_sender_id(sender)

    if not allow_phone_message(sender_id):
        logger.warning("Rate limit exceeded for %s", masked)
        return "rate limited"

    # LFPDPPP Oposición / CCPA: an opted-out user must not receive any
    # outbound message. We log that they messaged us (for audit
    # reconciliation) but stop before storing or replying.
    if inbox_service.is_opted_out(sender_id):
        logger.info("Opted-out sender silenced: %s", masked)
        return "opted out"

    message_type = message.get("type", "")

    contacts = value.get("contacts", [{}])
    raw_sender_name = contacts[0].get("profile", {}).get("name", "") if contacts else ""
    sender_name = sanitize_sender_name(raw_sender_name)

    incoming_text = ""
    if message_type == TEXT_MESSAGE_TYPE:
        incoming_text = str(message.get("text", {}).get("body", "") or "").strip()

    # The legacy inbox_messages schema keys on phone hash. BSUID storage
    # waits on the next schema migration; for now we only record phones
    # so the table doesn't accumulate rows we can't query consistently.
    if sender.is_phone:
        inbox_service.store_incoming_message(
            message_id,
            sender_id,
            sender_name,
            message_type,
            incoming_text,
        )

    if message_type == TEXT_MESSAGE_TYPE:
        lang = detect_language(incoming_text[:MAX_INCOMING_TEXT_CHARS])

        log_incoming_text_message(
            sender_name,
            sender_id,
            message_type,
            incoming_text,
        )

        if not incoming_text:
            whatsapp_client.send_whatsapp_message(
                sender_id,
                get_response("unknown_message", lang),
            )
            return "ok"

        if len(incoming_text) > MAX_INCOMING_TEXT_CHARS:
            logger.warning(
                "Incoming text too long from %s: length=%s",
                masked,
                len(incoming_text),
            )
            whatsapp_client.send_whatsapp_message(
                sender_id,
                get_message_too_long_response(lang),
            )
            return "ok"

        if incoming_text.upper() == HUMAN_HANDOFF_KEYWORD:
            response_text = get_response("human_handoff", lang)
            whatsapp_client.send_whatsapp_message(sender_id, response_text)
            whatsapp_client.notify_team(build_handoff_notification(sender_name, sender))
            logger.info("Human handoff requested by %s", masked)
            return "ok"

        opted_out, opt_out_keyword, opt_out_lang = is_opt_out_request(incoming_text)
        if opted_out:
            inbox_service.record_opt_out(
                sender_id,
                sender_external_id_type=sender.id_type,
                source="whatsapp_keyword",
                keyword_used=opt_out_keyword or "",
                language=opt_out_lang or lang,
            )
            confirmation = get_opt_out_confirmation_response(opt_out_lang or lang)
            whatsapp_client.send_whatsapp_message(sender_id, confirmation)
            logger.info(
                "Opt-out recorded for %s via keyword=%s",
                masked,
                opt_out_keyword,
            )
            return "opt out recorded"

        faq_answer = find_best_faq_match(incoming_text)

        if faq_answer:
            response_text = faq_answer
            logger.info("Responded via FAQ match")
        else:
            response_text = get_ai_response(incoming_text, sender_name)
            logger.info("Responded via AI")

        human_handoff_response = get_response("human_handoff", lang)
        if BOT_DISCLOSURE and not faq_answer and response_text != human_handoff_response:
            response_text += (
                "\n\n_This is an automated assistant. Reply HUMAN to speak with our team._"
            )

        whatsapp_client.send_whatsapp_message(sender_id, response_text)

    elif message_type in MEDIA_MESSAGE_TYPES:
        whatsapp_client.send_whatsapp_message(sender_id, get_response("media_response", "en"))
    else:
        whatsapp_client.send_whatsapp_message(sender_id, get_response("unknown_message", "en"))

    return "ok"
