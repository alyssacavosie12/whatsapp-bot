"""Orchestration for one inbound WhatsApp message."""

from __future__ import annotations

from typing import Any

from bot import whatsapp_client
from bot.ai_responder import get_ai_response
from bot.faq import find_best_faq_match
from bot.message_compliance import (
    record_opt_out_if_requested,
    store_incoming_for_inbox,
)
from bot.message_dispatch import dispatch_response_plan
from bot.message_intake import (
    intake_incoming_message,
    sanitize_sender_name,
)
from bot.message_logging import log_incoming_text_message
from bot.message_responses import (
    build_handoff_notification,
    get_message_too_long_response,
    get_opt_out_confirmation_response,
    get_privacy_notice_suffix,
    plan_message_response,
    with_first_contact_privacy_notice,
)
from inbox import service as inbox_service
from settings import (
    BOT_DISCLOSURE,
    INCOMING_MESSAGE_LOG_MAX_CHARS,
    LOG_INCOMING_MESSAGES,
    MAX_INCOMING_TEXT_CHARS,
)
from webhook.dedup import seen_message
from webhook.rate_limit import allow_phone_message

__all__ = [
    "build_handoff_notification",
    "get_message_too_long_response",
    "get_opt_out_confirmation_response",
    "get_privacy_notice_suffix",
    "log_incoming_text_message",
    "process_webhook_message",
    "sanitize_sender_name",
    "with_first_contact_privacy_notice",
]


def process_webhook_message(value: dict[str, Any], message: dict[str, Any]) -> str:
    """Process one WhatsApp message from a webhook payload."""
    intake = intake_incoming_message(
        value,
        message,
        seen_message=seen_message,
        allow_sender_message=allow_phone_message,
        is_opted_out=inbox_service.is_opted_out,
    )
    if intake.status:
        return intake.status

    incoming = intake.message
    if incoming is None:
        return "invalid sender"

    if record_opt_out_if_requested(
        incoming,
        record_opt_out=inbox_service.record_opt_out,
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
    dispatch_response_plan(
        incoming.sender_id,
        response_plan,
        send_message=whatsapp_client.send_whatsapp_message,
        notify_team=whatsapp_client.notify_team,
    )

    return response_plan.status