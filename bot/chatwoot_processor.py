"""Orchestration for inbound Chatwoot agent-bot messages."""

from __future__ import annotations

import logging
from typing import Any

from bot.ai_responder import get_ai_response
from bot.chatwoot_intake import (
    build_chatwoot_incoming_message,
    extract_chatwoot_sender_phone,
)
from bot.faq import find_best_faq_match
from bot.message_compliance import store_incoming_for_inbox
from bot.message_dispatch import dispatch_response_plan
from bot.message_logging import log_incoming_text_message
from bot.message_responses import plan_message_response
from bot.opt_out_keywords import is_opt_out_request
from bot.reply_sinks import ChatwootReplySink
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

__all__ = ["process_chatwoot_message"]


def _chatwoot_conversation_id(event: dict[str, Any]) -> int | str | None:
    conversation = event.get("conversation", {})
    if not isinstance(conversation, dict):
        logger.warning("Chatwoot event has non-dict conversation; skipping")
        return None

    conversation_id = conversation.get("id")
    if conversation_id in (None, "", 0):
        logger.warning("Chatwoot event missing conversation.id; skipping")
        return None

    return conversation_id


def _record_chatwoot_opt_out_if_requested(
    *,
    sender_id: str,
    sender_external_id_type: str,
    masked_sender: str,
    text: str,
) -> bool:
    """Record Chatwoot opt-out requests without sending a confirmation reply."""
    opted_out, opt_out_keyword, opt_out_lang = is_opt_out_request(text)
    if not opted_out:
        return False

    inbox_service.record_opt_out(
        sender_id,
        sender_external_id_type=sender_external_id_type,
        source="chatwoot_keyword",
        keyword_used=opt_out_keyword or "",
        language=opt_out_lang or "",
    )
    logger.info(
        "Opt-out recorded via Chatwoot for %s via keyword=%s",
        masked_sender,
        opt_out_keyword,
    )
    return True


def process_chatwoot_message(event: dict[str, Any]) -> str:
    """Process a Chatwoot agent-bot ``message_created`` event.

    Mirrors the safety contract of ``process_webhook_message`` for the
    Chatwoot transport: dedup, opt-out silence, rate limit, sensitive-text
    redaction, inbox persistence, FAQ/AI routing, and team handoff.
    """
    conversation_id = _chatwoot_conversation_id(event)
    if conversation_id is None:
        return "invalid event"

    message_id = str(event.get("id", "") or "")
    if message_id and seen_message(f"chatwoot:{message_id}"):
        logger.info(
            "Duplicate Chatwoot message ignored: %s",
            sanitize_untrusted_text(message_id, 80),
        )
        return "duplicate"

    sender_raw = extract_chatwoot_sender_phone(event)
    sender = parse_sender_id(sender_raw)
    if sender is None:
        logger.warning(
            "Chatwoot event with unrecognized sender id ignored: %s",
            sanitize_untrusted_text(sender_raw, 32) or "empty",
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

    incoming = build_chatwoot_incoming_message(
        event,
        sender=sender,
        masked_sender=masked,
    )

    # Strict opt-out: for Chatwoot we record and stop without confirmation.
    if incoming.is_text and _record_chatwoot_opt_out_if_requested(
        sender_id=sender_id,
        sender_external_id_type=sender.id_type,
        masked_sender=masked,
        text=incoming.text,
    ):
        return "opt out recorded"

    storage = store_incoming_for_inbox(
        incoming,
        is_first_contact=inbox_service.is_first_contact,
        store_incoming_message=inbox_service.store_incoming_message,
    )

    if incoming.is_text:
        log_incoming_text_message(
            incoming.sender_name,
            incoming.sender_id,
            incoming.message_type,
            incoming.text,
            log_text=LOG_INCOMING_MESSAGES,
            max_text_chars=INCOMING_MESSAGE_LOG_MAX_CHARS,
        )

    response_plan = plan_message_response(
        incoming,
        storage,
        faq_matcher=find_best_faq_match,
        ai_responder=get_ai_response,
        max_text_chars=MAX_INCOMING_TEXT_CHARS,
        bot_disclosure=BOT_DISCLOSURE,
    )

    sink = ChatwootReplySink(conversation_id=conversation_id)
    dispatch_response_plan(
        sender_id,
        response_plan,
        send_message=sink.send,
        notify_team=sink.notify_team,
    )

    return response_plan.status