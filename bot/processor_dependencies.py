"""Dependency container for inbound message processing."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, cast

from flask import Flask, current_app, has_app_context

from core.dependency_keys import MESSAGE_PROCESSOR_DEPENDENCIES_EXTENSION_KEY

SeenMessage = Callable[[str], bool]
AllowSenderMessage = Callable[[str], bool]
IsOptedOut = Callable[[str], bool]
IsFirstContact = Callable[[str], bool]
StoreIncomingMessage = Callable[[str, str, str, str, str], None]
FindFaqMatch = Callable[[str], str | None]
GetAiResponse = Callable[[str, str], str]
SendWhatsAppMessage = Callable[[str, str], object]
SendChatwootMessage = Callable[[int | str, str], object]
NotifyTeam = Callable[[str], object]
OptOutDetector = Callable[[str], tuple[bool, str | None, str | None]]

__all__ = [
    "AllowSenderMessage",
    "FindFaqMatch",
    "GetAiResponse",
    "IsFirstContact",
    "IsOptedOut",
    "MessageProcessorDependencies",
    "MessageProcessorSettings",
    "NotifyTeam",
    "OptOutDetector",
    "RecordOptOut",
    "SeenMessage",
    "SendChatwootMessage",
    "SendWhatsAppMessage",
    "StoreIncomingMessage",
    "install_message_processor_dependencies",
    "installed_message_processor_dependencies",
]


class RecordOptOut(Protocol):
    """Callable that records a sender opt-out.

    Implementations should be idempotent: webhook retries or duplicate inbound
    events may attempt to record the same opt-out more than once. Re-recording
    the same sender/source/keyword should not fail or create unsafe side
    effects.
    """

    def __call__(
        self,
        sender_external_id: str,
        *,
        sender_external_id_type: str = "phone",
        source: str,
        keyword_used: str = "",
        language: str = "",
    ) -> bool:
        """Record one opt-out request."""


@dataclass(frozen=True)
class MessageProcessorSettings:
    """Runtime settings needed by message processing."""

    bot_disclosure: bool
    incoming_message_log_max_chars: int
    log_incoming_messages: bool
    max_incoming_text_chars: int


@dataclass(frozen=True)
class MessageProcessorDependencies:
    """Injected collaborators for WhatsApp and Chatwoot message processing."""

    seen_message: SeenMessage
    allow_sender_message: AllowSenderMessage
    is_opted_out: IsOptedOut
    record_opt_out: RecordOptOut
    is_first_contact: IsFirstContact
    store_incoming_message: StoreIncomingMessage
    find_best_faq_match: FindFaqMatch
    get_ai_response: GetAiResponse
    send_whatsapp_message: SendWhatsAppMessage
    send_chatwoot_message: SendChatwootMessage
    notify_team: NotifyTeam
    is_opt_out_request: OptOutDetector
    settings: MessageProcessorSettings


def install_message_processor_dependencies(
    flask_app: Flask,
    dependencies: MessageProcessorDependencies,
) -> None:
    """Install message-processing dependencies into ``app.extensions``."""
    flask_app.extensions[MESSAGE_PROCESSOR_DEPENDENCIES_EXTENSION_KEY] = dependencies


def installed_message_processor_dependencies() -> MessageProcessorDependencies | None:
    """Return app-injected message-processing dependencies, when configured."""
    if not has_app_context():
        return None

    app = cast(Any, current_app)._get_current_object()
    dependencies = app.extensions.get(MESSAGE_PROCESSOR_DEPENDENCIES_EXTENSION_KEY)
    if dependencies is None:
        return None

    return cast(MessageProcessorDependencies, dependencies)
