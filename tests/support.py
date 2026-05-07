"""Helpers for tests that need to patch refactored application modules."""

from __future__ import annotations

from types import ModuleType
from typing import Any


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
            "hmac": [(webhook_routes, "hmac")],
            "inbox_csrf_token": [(inbox_service, "inbox_csrf_token")],
            "is_inbox_auth_limited": [(inbox_service, "is_inbox_auth_limited")],
            "list_inbox_messages": [(inbox_store, "list_messages")],
            "record_audit_event": [(inbox_store, "record_audit_event")],
            "record_inbox_auth_failure": [(inbox_service, "record_inbox_auth_failure")],
            "record_incoming_message": [(inbox_store, "record_incoming_message")],
            "record_opt_in_proof": [(inbox_store, "record_opt_in_proof")],
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

    return AppModuleProxy(app), app.create_app()
