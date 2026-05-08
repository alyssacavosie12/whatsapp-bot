"""Response routing for normalized inbound WhatsApp messages."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Final

from bot.content_loader import detect_language, get_response
from bot.message_intake import sanitize_sender_name
from bot.message_models import InboxStorageResult, IncomingMessage, ResponsePlan
from settings import PRIVACY_NOTICE_URL

logger = logging.getLogger(__name__)

HUMAN_HANDOFF_KEYWORD: Final = "HUMAN"
MEDIA_MESSAGE_TYPES: Final = {"image", "document", "audio", "video"}
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

FaqMatcher = Callable[[str], str | None]
AiResponder = Callable[[str, str], str]


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
    """Build a safe team alert for human handoff requests."""
    from core.sender_id import SenderId, parse_sender_id

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

    parsed = parse_sender_id(str(sender or ""))
    safe_phone = parsed.value if parsed and parsed.is_phone else "invalid"
    return (
        "HUMAN REQUESTED\n"
        f"Customer name: {safe_name}\n"
        f"Customer phone: +{safe_phone}\n"
        "Please respond to them directly."
    )


def _first_contact_reply(
    text: str,
    lang: str,
    storage: InboxStorageResult,
) -> str:
    """Apply first-contact disclosure to a reply when needed."""
    return with_first_contact_privacy_notice(
        text,
        lang,
        is_first_contact=storage.is_first_contact,
    )


def _plan_text_response(
    incoming: IncomingMessage,
    storage: InboxStorageResult,
    *,
    faq_matcher: FaqMatcher,
    ai_responder: AiResponder,
    max_text_chars: int,
    bot_disclosure: bool,
) -> ResponsePlan:
    """Return the reply plan for a text message."""
    lang = detect_language(incoming.text[:max_text_chars])

    if not incoming.text:
        return ResponsePlan(
            reply_text=_first_contact_reply(
                get_response("unknown_message", lang),
                lang,
                storage,
            )
        )

    if len(incoming.text) > max_text_chars:
        logger.warning(
            "Incoming text too long from %s: length=%s",
            incoming.masked_sender,
            len(incoming.text),
        )
        return ResponsePlan(
            reply_text=_first_contact_reply(
                get_message_too_long_response(lang),
                lang,
                storage,
            )
        )

    if incoming.text.upper() == HUMAN_HANDOFF_KEYWORD:
        return ResponsePlan(
            reply_text=_first_contact_reply(
                get_response("human_handoff", lang),
                lang,
                storage,
            ),
            team_notification=build_handoff_notification(
                incoming.sender_name,
                incoming.sender,
            ),
        )

    faq_answer = faq_matcher(incoming.text)

    if faq_answer:
        response_text = faq_answer
        logger.info("Responded via FAQ match")
    elif storage.sensitive_category:
        response_text = get_response("human_handoff", lang)
        logger.info(
            "Sensitive message routed to human handoff: sender=%s category=%s",
            incoming.masked_sender,
            storage.sensitive_category,
        )
        return ResponsePlan(
            reply_text=_first_contact_reply(response_text, lang, storage),
            team_notification=build_handoff_notification(
                incoming.sender_name,
                incoming.sender,
            ),
        )
    else:
        response_text = ai_responder(incoming.text, incoming.sender_name)
        logger.info("Responded via AI")

    human_handoff_response = get_response("human_handoff", lang)
    if bot_disclosure and not faq_answer and response_text != human_handoff_response:
        response_text += "\n\n_This is an automated assistant. Reply HUMAN to speak with our team._"

    return ResponsePlan(
        reply_text=_first_contact_reply(response_text, lang, storage),
    )


def plan_message_response(
    incoming: IncomingMessage,
    storage: InboxStorageResult,
    *,
    faq_matcher: FaqMatcher,
    ai_responder: AiResponder,
    max_text_chars: int,
    bot_disclosure: bool,
) -> ResponsePlan:
    """Route a normalized inbound message to a response plan."""
    if incoming.is_text:
        return _plan_text_response(
            incoming,
            storage,
            faq_matcher=faq_matcher,
            ai_responder=ai_responder,
            max_text_chars=max_text_chars,
            bot_disclosure=bot_disclosure,
        )

    if incoming.message_type in MEDIA_MESSAGE_TYPES:
        return ResponsePlan(
            reply_text=_first_contact_reply(
                get_response("media_response", "en"),
                "en",
                storage,
            )
        )

    return ResponsePlan(
        reply_text=_first_contact_reply(
            get_response("unknown_message", "en"),
            "en",
            storage,
        )
    )
