"""Processing for one inbound WhatsApp message."""

from __future__ import annotations

import logging
from typing import Any, Final

from bot import whatsapp_client
from bot.ai_responder import get_ai_response
from bot.content_loader import detect_language, get_response
from bot.faq import find_best_faq_match
from bot.opt_out_keywords import is_opt_out_request
from bot.sensitive_filter import (
    SENSITIVE_REDACTED_MESSAGE_TYPE,
    classify_sensitive_message,
    redacted_sensitive_body,
)
from core.phone_utils import mask_phone
from core.sender_id import mask_sender_id, parse_sender_id
from core.text_utils import sanitize_untrusted_text
from inbox import service as inbox_service
from settings import (
    BOT_DISCLOSURE,
    INCOMING_MESSAGE_LOG_MAX_CHARS,
    LOG_INCOMING_MESSAGES,
    MAX_INCOMING_TEXT_CHARS,
    PRIVACY_NOTICE_URL,
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
PRIVACY_NOTICE_SUFFIX_FALLBACK: Final[dict[str, str]] = {
    "en": f"By chatting with us, you agree to our Privacy Notice: {PRIVACY_NOTICE_URL}",
    "es": f"Al chatear con nosotros, aceptas nuestro Aviso de Privacidad: {PRIVACY_NOTICE_URL}",
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


def get_privacy_notice_suffix(lang: str) -> str:
    """Return the localized Privacy Notice line for first-contact replies."""
    return get_response("privacy_notice_suffix", lang) or PRIVACY_NOTICE_SUFFIX_FALLBACK[lang]


def with_first_contact_privacy_notice(
    response_text: str,
    lang: str,
    *,
    is_first_contact: bool,
) -> str:
    """Append Privacy Notice disclosure to the first response for a sender."""
    if not is_first_contact:
        return response_text

    suffix = get_privacy_notice_suffix(lang)
    if not suffix:
        return response_text

    return f"{response_text}\n\n{suffix}"


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

    # LFPDPPP Oposición / CCPA: an opted-out user must not receive any
    # outbound message. We log that they messaged us (for audit
    # reconciliation) but stop before storing or replying.
    if inbox_service.is_opted_out(sender_id):
        logger.info("Opted-out sender silenced: %s", masked)
        return "opted out"

    if not allow_phone_message(sender_id):
        logger.warning("Rate limit exceeded for %s", masked)
        return "rate limited"

    message_type = message.get("type", "")

    contacts = value.get("contacts", [{}])
    raw_sender_name = contacts[0].get("profile", {}).get("name", "") if contacts else ""
    sender_name = sanitize_sender_name(raw_sender_name)

    incoming_text = ""
    if message_type == TEXT_MESSAGE_TYPE:
        incoming_text = str(message.get("text", {}).get("body", "") or "").strip()

    # Strict opt-out (LFPDPPP Oposición / CCPA / Meta): do not send any
    # confirmation message. Record the opt-out and stop processing before
    # inbox persistence or AI/FAQ.
    if message_type == TEXT_MESSAGE_TYPE:
        opted_out, opt_out_keyword, opt_out_lang = is_opt_out_request(incoming_text)
        if opted_out:
            inbox_service.record_opt_out(
                sender_id,
                sender_external_id_type=sender.id_type,
                source="whatsapp_keyword",
                keyword_used=opt_out_keyword or "",
                language=opt_out_lang or "",
            )
            logger.info(
                "Opt-out recorded for %s via keyword=%s",
                masked,
                opt_out_keyword,
            )
            return "opt out recorded"

    sensitive_category = (
        classify_sensitive_message(incoming_text) if message_type == TEXT_MESSAGE_TYPE else None
    )
    stored_message_type = SENSITIVE_REDACTED_MESSAGE_TYPE if sensitive_category else message_type
    stored_body = (
        redacted_sensitive_body(sensitive_category) if sensitive_category else incoming_text
    )

    # Persist inbound messages for the admin inbox (phones and BSUID). Sensitive
    # text is replaced by a category marker before it reaches Postgres.
    is_first_contact = inbox_service.is_first_contact(sender_id)
    inbox_service.store_incoming_message(
        message_id,
        sender_id,
        sender_name,
        stored_message_type,
        stored_body,
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
                with_first_contact_privacy_notice(
                    get_response("unknown_message", lang),
                    lang,
                    is_first_contact=is_first_contact,
                ),
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
                with_first_contact_privacy_notice(
                    get_message_too_long_response(lang),
                    lang,
                    is_first_contact=is_first_contact,
                ),
            )
            return "ok"

        if incoming_text.upper() == HUMAN_HANDOFF_KEYWORD:
            response_text = get_response("human_handoff", lang)
            response_text = with_first_contact_privacy_notice(
                response_text,
                lang,
                is_first_contact=is_first_contact,
            )
            whatsapp_client.send_whatsapp_message(sender_id, response_text)
            whatsapp_client.notify_team(build_handoff_notification(sender_name, sender))
            logger.info("Human handoff requested by %s", masked)
            return "ok"

        faq_answer = find_best_faq_match(incoming_text)

        if faq_answer:
            response_text = faq_answer
            logger.info("Responded via FAQ match")
        elif sensitive_category:
            response_text = get_response("human_handoff", lang)
            whatsapp_client.notify_team(build_handoff_notification(sender_name, sender))
            logger.info(
                "Sensitive message routed to human handoff: sender=%s category=%s",
                masked,
                sensitive_category,
            )
        else:
            response_text = get_ai_response(incoming_text, sender_name)
            logger.info("Responded via AI")

        human_handoff_response = get_response("human_handoff", lang)
        if BOT_DISCLOSURE and not faq_answer and response_text != human_handoff_response:
            response_text += (
                "\n\n_This is an automated assistant. Reply HUMAN to speak with our team._"
            )

        response_text = with_first_contact_privacy_notice(
            response_text,
            lang,
            is_first_contact=is_first_contact,
        )
        whatsapp_client.send_whatsapp_message(sender_id, response_text)

    elif message_type in MEDIA_MESSAGE_TYPES:
        whatsapp_client.send_whatsapp_message(
            sender_id,
            with_first_contact_privacy_notice(
                get_response("media_response", "en"),
                "en",
                is_first_contact=is_first_contact,
            ),
        )
    else:
        whatsapp_client.send_whatsapp_message(
            sender_id,
            with_first_contact_privacy_notice(
                get_response("unknown_message", "en"),
                "en",
                is_first_contact=is_first_contact,
            ),
        )

    return "ok"


def process_call_event(value: dict[str, Any], call: dict[str, Any]) -> str:
    """Process one WhatsApp call event from a webhook payload.

    Sends a courteous auto-reply to the caller letting them know the missed
    call was received and where to book or chat. Notifies the team if a
    notification phone is configured. Mirrors the safety guarantees used
    for inbound messages: opted-out callers are silenced, rate-limited
    callers are dropped, and untrusted strings are never logged unmasked.
    """
    call_id = call.get("id", "")

    if call_id and seen_message(call_id):
        logger.info(
            "Duplicate call ignored: %s",
            sanitize_untrusted_text(call_id, 80),
        )
        return "duplicate"

    caller_raw = call.get("from", "")
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


# ─── Transport abstraction (Protocol) ──────────────────────────────
#
# A ReplySink decouples the bot's outbound message logic from the specific
# transport (Meta Cloud API vs Chatwoot). The existing
# ``process_webhook_message`` hot path still uses ``whatsapp_client``
# directly to keep this PR's diff bounded; a follow-up refactor will
# migrate it to use the same sink protocol so the shared dispatch logic
# can be extracted. Tests can inject a fake sink to assert outbound text
# without mocking module-level functions.

from dataclasses import dataclass  # noqa: E402  (kept near usage)
from typing import Protocol  # noqa: E402

from bot import chatwoot_client  # noqa: E402
from settings import (  # noqa: E402
    CHATWOOT_ACCOUNT_ID,
    CHATWOOT_API_TOKEN,
    CHATWOOT_TRANSPORT,
    CHATWOOT_WEBHOOK_SECRET,
)


class ReplySink(Protocol):
    """Outbound message destination for the bot.

    Implementations carry just enough state to route a reply back to the
    caller of an inbound message (recipient phone for Meta, conversation
    id for Chatwoot).
    """

    def send(self, text: str) -> None:
        """Deliver ``text`` to the originating customer."""

    def notify_team(self, message: str) -> None:
        """Send an internal alert to the operations channel."""


@dataclass(frozen=True)
class WhatsAppReplySink:
    """ReplySink that delivers via Meta Cloud API (existing transport)."""

    recipient_id: str

    def send(self, text: str) -> None:
        whatsapp_client.send_whatsapp_message(self.recipient_id, text)

    def notify_team(self, message: str) -> None:
        whatsapp_client.notify_team(message)


@dataclass(frozen=True)
class ChatwootReplySink:
    """ReplySink that delivers via Chatwoot's agent-bot REST API.

    Team notifications continue to flow through ``whatsapp_client``: the
    on-call operator's notification phone is a Meta-side concept and is
    independent of the customer-facing transport.
    """

    conversation_id: int | str

    def send(self, text: str) -> None:
        chatwoot_client.send_message(self.conversation_id, text)

    def notify_team(self, message: str) -> None:
        whatsapp_client.notify_team(message)


# ─── Chatwoot agent-bot incoming message handler ───────────────────


CHATWOOT_REQUIRED_ENV_VARS: Final = (
    "CHATWOOT_API_TOKEN",
    "CHATWOOT_ACCOUNT_ID",
    "CHATWOOT_WEBHOOK_SECRET",
)


def chatwoot_transport_misconfiguration() -> str | None:
    """Return a reason string when CHATWOOT_TRANSPORT is on but config is bad.

    Used by the Flask app factory to fail loudly at boot rather than
    discovering a missing env var on the first webhook delivery.
    """
    if not CHATWOOT_TRANSPORT:
        return None

    missing = []
    if not CHATWOOT_API_TOKEN:
        missing.append("CHATWOOT_API_TOKEN")
    if not CHATWOOT_ACCOUNT_ID:
        missing.append("CHATWOOT_ACCOUNT_ID")
    if not CHATWOOT_WEBHOOK_SECRET:
        missing.append("CHATWOOT_WEBHOOK_SECRET")

    if missing:
        return f"CHATWOOT_TRANSPORT is enabled but missing env vars: {', '.join(missing)}"

    return None


def _extract_chatwoot_sender_phone(event: dict[str, Any]) -> str:
    """Pull the customer's phone number from a Chatwoot message_created event.

    Chatwoot's payload exposes the contact under ``sender`` and (more
    completely) under ``conversation.meta.sender``. We try both. The
    leading ``+`` of an E.164 number is stripped because the bot's
    ``parse_sender_id`` expects digit-only WhatsApp recipient ids; BSUIDs
    or non-phone identifiers are returned verbatim for downstream
    classification.
    """
    candidate = ""

    direct_sender = event.get("sender", {})
    if isinstance(direct_sender, dict):
        phone = direct_sender.get("phone_number") or direct_sender.get("identifier")
        if isinstance(phone, str) and phone:
            candidate = phone

    if not candidate:
        meta = event.get("conversation", {})
        if isinstance(meta, dict):
            nested = meta.get("meta", {})
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


def process_chatwoot_message(event: dict[str, Any]) -> str:
    """Process a Chatwoot agent-bot ``message_created`` event.

    Mirrors the safety contract of :func:`process_webhook_message` for the
    Chatwoot transport: dedup, opt-out silence, rate limit, sensitive-text
    redaction, and inbox persistence. Reuses the same FAQ/AI dispatch
    logic via the shared bot modules.
    """
    conversation = event.get("conversation", {})
    if not isinstance(conversation, dict):
        logger.warning("Chatwoot event has non-dict conversation; skipping")
        return "invalid event"

    conversation_id = conversation.get("id")
    if conversation_id in (None, "", 0):
        logger.warning("Chatwoot event missing conversation.id; skipping")
        return "invalid event"

    message_id = str(event.get("id", "") or "")
    if message_id and seen_message(f"chatwoot:{message_id}"):
        logger.info("Duplicate Chatwoot message ignored: %s", message_id)
        return "duplicate"

    sender_phone = _extract_chatwoot_sender_phone(event)
    sender = parse_sender_id(sender_phone)
    if sender is None:
        logger.warning(
            "Chatwoot event with unrecognized sender id ignored: %s",
            sanitize_untrusted_text(sender_phone, 32) or "empty",
        )
        return "invalid sender"

    sender_id = sender.value
    masked = mask_sender_id(sender)

    if inbox_service.is_opted_out(sender_id):
        logger.info("Opted-out Chatwoot sender silenced: %s", masked)
        return "opted out"

    if not allow_phone_message(sender_id):
        logger.warning("Rate limit exceeded for Chatwoot sender %s", masked)
        return "rate limited"

    sink = ChatwootReplySink(conversation_id=conversation_id)

    sender_data = event.get("sender", {})
    raw_sender_name = sender_data.get("name", "") if isinstance(sender_data, dict) else ""
    sender_name = sanitize_sender_name(raw_sender_name)

    incoming_text = str(event.get("content", "") or "").strip()
    content_type = str(event.get("content_type", "") or "")
    is_text = bool(incoming_text) and content_type in ("", "text")

    sensitive_category = (
        classify_sensitive_message(incoming_text) if is_text else None
    )
    stored_message_type = (
        SENSITIVE_REDACTED_MESSAGE_TYPE
        if sensitive_category
        else (TEXT_MESSAGE_TYPE if is_text else "non_text")
    )
    stored_body = (
        redacted_sensitive_body(sensitive_category) if sensitive_category else incoming_text
    )

    is_first_contact = inbox_service.is_first_contact(sender_id)
    inbox_service.store_incoming_message(
        message_id,
        sender_id,
        sender_name,
        stored_message_type,
        stored_body,
    )

    # Strict opt-out (LFPDPPP / CCPA / Meta): no confirmation reply.
    if is_text:
        opted_out, opt_out_keyword, opt_out_lang = is_opt_out_request(incoming_text)
        if opted_out:
            inbox_service.record_opt_out(
                sender_id,
                sender_external_id_type=sender.id_type,
                source="chatwoot_keyword",
                keyword_used=opt_out_keyword or "",
                language=opt_out_lang or "",
            )
            logger.info(
                "Opt-out recorded via Chatwoot for %s via keyword=%s",
                masked,
                opt_out_keyword,
            )
            return "opt out recorded"

    if not is_text:
        sink.send(
            with_first_contact_privacy_notice(
                get_response("media_response", "en"),
                "en",
                is_first_contact=is_first_contact,
            )
        )
        return "ok"

    lang = detect_language(incoming_text[:MAX_INCOMING_TEXT_CHARS])

    log_incoming_text_message(
        sender_name,
        sender_id,
        TEXT_MESSAGE_TYPE,
        incoming_text,
    )

    if len(incoming_text) > MAX_INCOMING_TEXT_CHARS:
        logger.warning(
            "Chatwoot incoming text too long from %s: length=%s",
            masked,
            len(incoming_text),
        )
        sink.send(
            with_first_contact_privacy_notice(
                get_message_too_long_response(lang),
                lang,
                is_first_contact=is_first_contact,
            )
        )
        return "ok"

    if incoming_text.upper() == HUMAN_HANDOFF_KEYWORD:
        response_text = with_first_contact_privacy_notice(
            get_response("human_handoff", lang),
            lang,
            is_first_contact=is_first_contact,
        )
        sink.send(response_text)
        sink.notify_team(build_handoff_notification(sender_name, sender))
        logger.info("Human handoff requested via Chatwoot by %s", masked)
        return "ok"

    faq_answer = find_best_faq_match(incoming_text)

    if faq_answer:
        response_text = faq_answer
        logger.info("Chatwoot reply via FAQ match")
    elif sensitive_category:
        response_text = get_response("human_handoff", lang)
        sink.notify_team(build_handoff_notification(sender_name, sender))
        logger.info(
            "Sensitive Chatwoot message routed to human handoff: sender=%s category=%s",
            masked,
            sensitive_category,
        )
    else:
        response_text = get_ai_response(incoming_text, sender_name)
        logger.info("Chatwoot reply via AI")

    human_handoff_response = get_response("human_handoff", lang)
    if BOT_DISCLOSURE and not faq_answer and response_text != human_handoff_response:
        response_text += (
            "\n\n_This is an automated assistant. Reply HUMAN to speak with our team._"
        )

    response_text = with_first_contact_privacy_notice(
        response_text,
        lang,
        is_first_contact=is_first_contact,
    )
    sink.send(response_text)
    return "ok"
