"""Orchestration for one inbound WhatsApp message.

This module is the primary WhatsApp message orchestrator. It also keeps a thin
backwards-compatibility facade for older imports that historically reached
Chatwoot/call helpers through ``bot.message_processor``.
"""

from __future__ import annotations

from typing import Any

from bot import chatwoot_client, whatsapp_client
from bot.ai_responder import get_ai_response
from bot.call_processor import process_call_event
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
from bot.opt_out_keywords import is_opt_out_request
from bot.processor_dependencies import (
    MessageProcessorDependencies,
    MessageProcessorSettings,
    installed_message_processor_dependencies,
)
from inbox import service as inbox_service
from settings import (
    BOT_DISCLOSURE,
    CHATWOOT_ACCOUNT_ID,
    CHATWOOT_API_TOKEN,
    CHATWOOT_TRANSPORT,
    CHATWOOT_WEBHOOK_SECRET,
    INCOMING_MESSAGE_LOG_MAX_CHARS,
    LOG_INCOMING_MESSAGES,
    MAX_INCOMING_TEXT_CHARS,
)
from webhook.dedup import seen_message
from webhook.rate_limit import allow_phone_message

# Backwards compatibility only:
# Older tests and modules patch/import several dependencies through
# bot.message_processor. New code should import concrete dependencies from
# their owning modules, e.g. bot.chatwoot_client, webhook.dedup, or settings.
__all__ = [
    "BOT_DISCLOSURE",
    "CHATWOOT_ACCOUNT_ID",
    "CHATWOOT_API_TOKEN",
    "CHATWOOT_TRANSPORT",
    "CHATWOOT_WEBHOOK_SECRET",
    "INCOMING_MESSAGE_LOG_MAX_CHARS",
    "LOG_INCOMING_MESSAGES",
    "MAX_INCOMING_TEXT_CHARS",
    "allow_phone_message",
    "build_handoff_notification",
    "chatwoot_client",
    "chatwoot_transport_misconfiguration",
    "find_best_faq_match",
    "get_ai_response",
    "get_message_too_long_response",
    "get_opt_out_confirmation_response",
    "get_privacy_notice_suffix",
    "inbox_service",
    "is_opt_out_request",
    "log_incoming_text_message",
    "process_call_event",
    "process_chatwoot_message",
    "process_webhook_message",
    "resolve_message_processor_dependencies",
    "sanitize_sender_name",
    "seen_message",
    "whatsapp_client",
    "with_first_contact_privacy_notice",
]


def chatwoot_transport_misconfiguration() -> str | None:
    """Return Chatwoot config errors using this module's patchable globals."""
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


def _module_dependencies() -> MessageProcessorDependencies:
    """Build dependencies from module globals for CLI use and legacy tests."""
    return MessageProcessorDependencies(
        seen_message=seen_message,
        allow_sender_message=allow_phone_message,
        is_opted_out=inbox_service.is_opted_out,
        record_opt_out=inbox_service.record_opt_out,
        is_first_contact=inbox_service.is_first_contact,
        store_incoming_message=inbox_service.store_incoming_message,
        find_best_faq_match=find_best_faq_match,
        get_ai_response=get_ai_response,
        send_whatsapp_message=whatsapp_client.send_whatsapp_message,
        send_chatwoot_message=chatwoot_client.send_message,
        notify_team=whatsapp_client.notify_team,
        is_opt_out_request=is_opt_out_request,
        settings=MessageProcessorSettings(
            bot_disclosure=BOT_DISCLOSURE,
            incoming_message_log_max_chars=INCOMING_MESSAGE_LOG_MAX_CHARS,
            log_incoming_messages=LOG_INCOMING_MESSAGES,
            max_incoming_text_chars=MAX_INCOMING_TEXT_CHARS,
        ),
    )


def resolve_message_processor_dependencies(
    dependencies: MessageProcessorDependencies | None = None,
) -> MessageProcessorDependencies:
    """Return explicit, app-injected, or module-default message dependencies."""
    if dependencies is not None:
        return dependencies

    installed_dependencies = installed_message_processor_dependencies()
    if installed_dependencies is not None:
        return installed_dependencies

    return _module_dependencies()


def process_webhook_message(
    value: dict[str, Any],
    message: dict[str, Any],
    dependencies: MessageProcessorDependencies | None = None,
) -> str:
    """Process one WhatsApp message from a webhook payload."""
    deps = resolve_message_processor_dependencies(dependencies)
    intake = intake_incoming_message(
        value,
        message,
        seen_message=deps.seen_message,
        allow_sender_message=deps.allow_sender_message,
        is_opted_out=deps.is_opted_out,
    )
    if intake.status:
        return intake.status

    incoming = intake.message

    # Safety net: intake.status should be set whenever message is None. Keep
    # this guard so a malformed custom IntakeResult does not crash processing.
    if incoming is None:
        return "invalid sender"

    if record_opt_out_if_requested(
        incoming,
        record_opt_out=deps.record_opt_out,
        opt_out_detector=deps.is_opt_out_request,
    ):
        return "opt out recorded"

    storage = store_incoming_for_inbox(
        incoming,
        is_first_contact=deps.is_first_contact,
        store_incoming_message=deps.store_incoming_message,
    )

    if incoming.is_text:
        log_incoming_text_message(
            incoming.sender_name,
            incoming.sender_id,
            incoming.message_type,
            incoming.text,
            log_text=deps.settings.log_incoming_messages,
            max_text_chars=deps.settings.incoming_message_log_max_chars,
        )

    response_plan = plan_message_response(
        incoming,
        storage,
        faq_matcher=deps.find_best_faq_match,
        ai_responder=deps.get_ai_response,
        max_text_chars=deps.settings.max_incoming_text_chars,
        bot_disclosure=deps.settings.bot_disclosure,
    )
    dispatch_response_plan(
        incoming.sender_id,
        response_plan,
        send_message=deps.send_whatsapp_message,
        notify_team=deps.notify_team,
    )

    return response_plan.status


def process_chatwoot_message(
    event: dict[str, Any],
    dependencies: MessageProcessorDependencies | None = None,
) -> str:
    """Compatibility wrapper for Chatwoot agent-bot message processing.

    New code should import ``process_chatwoot_message`` directly from
    ``bot.chatwoot_processor``.
    """
    from bot.chatwoot_processor import process_chatwoot_message as _process_chatwoot_message

    return _process_chatwoot_message(event, dependencies=dependencies)
