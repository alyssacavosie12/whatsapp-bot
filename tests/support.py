"""Helpers for tests that need to patch refactored application modules."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import ModuleType
from typing import Any, cast

from bot.processor_dependencies import MessageProcessorDependencies, MessageProcessorSettings


class AppModuleProxy:
    """Compatibility proxy that routes old app-level patches to new modules."""

    def __init__(self, app_module: ModuleType) -> None:
        object.__setattr__(self, "_app", app_module)
        object.__setattr__(self, "_patch_map", self._build_patch_map())

    def _build_patch_map(self) -> dict[str, list[tuple[ModuleType, str]]]:
        from bot import message_processor, whatsapp_client
        from inbox import routes as inbox_routes
        from inbox import service as inbox_service
        from inbox import store as inbox_store
        from webhook import routes as webhook_routes
        from webhook import signature as webhook_signature

        return {
            "GRAPH_API_VERSION": [(whatsapp_client, "GRAPH_API_VERSION")],
            "INBOX_ADMIN_PASSWORD_HASH": [(inbox_service, "INBOX_ADMIN_PASSWORD_HASH")],
            "INBOX_ADMIN_USERNAME": [(inbox_service, "INBOX_ADMIN_USERNAME")],
            "INBOX_CSRF_SECRET": [(inbox_service, "INBOX_CSRF_SECRET")],
            "INBOX_DATABASE_URL": [
                (inbox_service, "INBOX_DATABASE_URL"),
                (inbox_routes, "INBOX_DATABASE_URL"),
            ],
            "INBOX_ENABLED": [(inbox_service, "INBOX_ENABLED")],
            "INBOX_ENCRYPTION_KEY": [
                (inbox_service, "INBOX_ENCRYPTION_KEY"),
                (inbox_routes, "INBOX_ENCRYPTION_KEY"),
            ],
            "INBOX_PROOF_SECRET": [(inbox_service, "INBOX_PROOF_SECRET")],
            "INBOX_REQUIRE_ENCRYPTION": [(inbox_service, "INBOX_REQUIRE_ENCRYPTION")],
            "INBOX_RETENTION_DAYS": [(inbox_service, "INBOX_RETENTION_DAYS")],
            "INBOX_VIEWER_PASSWORD_HASH": [(inbox_service, "INBOX_VIEWER_PASSWORD_HASH")],
            "INBOX_VIEWER_USERNAME": [(inbox_service, "INBOX_VIEWER_USERNAME")],
            "INCOMING_MESSAGE_LOG_MAX_CHARS": [
                (message_processor, "INCOMING_MESSAGE_LOG_MAX_CHARS")
            ],
            "LOG_INCOMING_MESSAGES": [(message_processor, "LOG_INCOMING_MESSAGES")],
            "MAX_INCOMING_TEXT_CHARS": [(message_processor, "MAX_INCOMING_TEXT_CHARS")],
            "META_APP_SECRET": [
                (inbox_service, "META_APP_SECRET"),
                (webhook_signature, "META_APP_SECRET"),
            ],
            "TEAM_NOTIFY_PHONE": [(whatsapp_client, "TEAM_NOTIFY_PHONE")],
            "VERIFY_TOKEN": [(webhook_routes, "VERIFY_TOKEN")],
            "WHATSAPP_PHONE_NUMBER_ID": [(whatsapp_client, "WHATSAPP_PHONE_NUMBER_ID")],
            "WHATSAPP_TOKEN": [(whatsapp_client, "WHATSAPP_TOKEN")],
            "allow_phone_message": [(message_processor, "allow_phone_message")],
            "find_best_faq_match": [(message_processor, "find_best_faq_match")],
            "get_ai_response": [(message_processor, "get_ai_response")],
            "get_message_by_id": [(inbox_store, "get_message_by_id")],
            "hmac": [(webhook_routes, "hmac")],
            "inbox_csrf_token": [(inbox_service, "inbox_csrf_token")],
            "is_first_contact": [(inbox_service, "is_first_contact")],
            "is_inbox_auth_limited": [(inbox_service, "is_inbox_auth_limited")],
            "list_inbox_messages": [(inbox_store, "list_messages")],
            "record_audit_event": [(inbox_store, "record_audit_event")],
            "record_inbox_auth_failure": [(inbox_service, "record_inbox_auth_failure")],
            "record_incoming_message": [(inbox_store, "record_incoming_message")],
            "record_opt_in_proof": [(inbox_store, "record_opt_in_proof")],
            "run_store_in_background": [(inbox_service, "run_store_in_background")],
            "requests": [(whatsapp_client, "requests")],
            "seen_message": [(message_processor, "seen_message")],
            "send_whatsapp_message": [(whatsapp_client, "send_whatsapp_message")],
            "soft_delete_message": [(inbox_store, "soft_delete_message")],
            "verify_meta_signature": [(webhook_signature, "verify_meta_signature")],
        }

    def __getattr__(self, name: str) -> Any:
        patch_map: dict[str, list[tuple[ModuleType, str]]] = object.__getattribute__(
            self, "_patch_map"
        )
        if name in patch_map:
            module, attr = patch_map[name][0]
            return getattr(module, attr)

        app_module: ModuleType = object.__getattribute__(self, "_app")
        return getattr(app_module, name)

    def __setattr__(self, name: str, value: Any) -> None:
        patch_map: dict[str, list[tuple[ModuleType, str]]] = object.__getattribute__(
            self, "_patch_map"
        )
        if name in patch_map:
            for module, attr in patch_map[name]:
                setattr(module, attr, value)
            return

        app_module: ModuleType = object.__getattribute__(self, "_app")
        setattr(app_module, name, value)


def make_app_modules() -> tuple[AppModuleProxy, Any]:
    """Return a compatibility module proxy and a fresh Flask app."""
    import app
    from inbox import service as inbox_service
    from webhook import routes as webhook_routes

    def run_webhook_inline(target: Any, events: Any) -> None:
        target(events)

    def run_store_inline(target: Any, *args: Any) -> None:
        target(*args)

    def returning_contact(_sender: str) -> bool:
        return False

    webhook_routes.run_in_background = cast(Any, run_webhook_inline)
    inbox_service.run_store_in_background = cast(Any, run_store_inline)
    inbox_service.is_first_contact = cast(Any, returning_contact)
    return AppModuleProxy(app), app.create_app()


@dataclass
class MessageProcessorHarness:
    """Captured side effects for dependency-injected processor tests."""

    sent: list[tuple[str, str]] = field(default_factory=list)
    chatwoot_sent: list[tuple[int | str, str]] = field(default_factory=list)
    notifications: list[str] = field(default_factory=list)
    stored: list[tuple[str, str, str, str, object]] = field(default_factory=list)
    opt_outs: list[tuple[str, dict[str, Any]]] = field(default_factory=list)


def make_message_dependencies(
    **overrides: Any,
) -> tuple[MessageProcessorDependencies, MessageProcessorHarness]:
    """Return injectable message dependencies plus captured side effects."""
    harness = MessageProcessorHarness()

    def record_opt_out(sender_external_id: str, **kwargs: Any) -> bool:
        harness.opt_outs.append((sender_external_id, kwargs))
        return True

    def store_incoming_message(
        message_id: str,
        sender_id: str,
        sender_name: str,
        message_type: str,
        body: object,
    ) -> None:
        harness.stored.append((message_id, sender_id, sender_name, message_type, body))

    dependencies = MessageProcessorDependencies(
        seen_message=lambda _message_id: False,
        allow_sender_message=lambda _sender_id: True,
        is_opted_out=lambda _sender_id: False,
        record_opt_out=record_opt_out,
        is_first_contact=lambda _sender_id: False,
        store_incoming_message=store_incoming_message,
        find_best_faq_match=lambda _text: "FAQ response",
        get_ai_response=lambda _text, _sender_name: "AI response",
        send_whatsapp_message=lambda sender_id, text: harness.sent.append((sender_id, text)),
        send_chatwoot_message=lambda conversation_id, text: harness.chatwoot_sent.append(
            (conversation_id, text)
        ),
        notify_team=lambda message: harness.notifications.append(message),
        is_opt_out_request=lambda _text: (False, None, None),
        settings=MessageProcessorSettings(
            bot_disclosure=False,
            incoming_message_log_max_chars=120,
            log_incoming_messages=False,
            max_incoming_text_chars=8000,
        ),
    )
    return replace(dependencies, **overrides), harness
