"""Small dependency-injection tests for message processing."""

from __future__ import annotations

from typing import Any

from tests.support import make_message_dependencies

VALUE: dict[str, Any] = {"contacts": [{"profile": {"name": "Maria"}}]}
WHATSAPP_MESSAGE: dict[str, Any] = {
    "id": "wamid.di.1",
    "from": "37368826828",
    "type": "text",
    "text": {"body": "price"},
}
CHATWOOT_EVENT: dict[str, Any] = {
    "id": 55,
    "conversation": {"id": 42},
    "sender": {"phone_number": "+529841050808", "name": "Maria"},
    "content": "price",
    "content_type": "text",
}


def test_webhook_processor_accepts_injected_dependencies(content_file: Any) -> None:
    from bot.message_processor import process_webhook_message

    deps, harness = make_message_dependencies(find_best_faq_match=lambda _text: "Injected FAQ")
    assert process_webhook_message(VALUE, WHATSAPP_MESSAGE, deps) == "ok"
    assert harness.sent == [("37368826828", "Injected FAQ")]


def test_chatwoot_processor_accepts_injected_dependencies(content_file: Any) -> None:
    from bot.message_processor import process_chatwoot_message

    deps, harness = make_message_dependencies(find_best_faq_match=lambda _text: "Injected FAQ")
    assert process_chatwoot_message(CHATWOOT_EVENT, deps) == "ok"
    assert harness.chatwoot_sent == [(42, "Injected FAQ")]


def test_app_factory_installs_message_processor_dependencies(content_file: Any) -> None:
    from app import create_app
    from bot.message_processor import process_webhook_message

    deps, harness = make_message_dependencies(find_best_faq_match=lambda _text: "App DI FAQ")
    with create_app(message_dependencies=deps).app_context():
        assert process_webhook_message(VALUE, WHATSAPP_MESSAGE) == "ok"
    assert harness.sent == [("37368826828", "App DI FAQ")]
