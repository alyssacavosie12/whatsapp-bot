"""End-to-end tests for the Chatwoot agent-bot route + process_chatwoot_message."""

from __future__ import annotations

import hashlib
import hmac
import json
from itertools import count
from typing import Any

import pytest

from bot import message_processor
from tests.support import make_app_modules
from webhook import chatwoot_routes, chatwoot_signature

SECRET = "test-chatwoot-secret"
PHONE = "+529841050808"
NORMALIZED_PHONE = "529841050808"

_ids = count(1)


def _digest(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _headers(body: bytes, secret: str = SECRET) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Chatwoot-Signature": _digest(body, secret),
    }


def _event(
    *,
    event: str = "message_created",
    message_type: str = "incoming",
    private: bool = False,
    content: str = "what is botox?",
    content_type: str = "text",
    conversation_id: int | None = 42,
    sender_phone: str | None = PHONE,
    sender_name: str = "Maria",
    message_id: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event": event,
        "message_type": message_type,
        "private": private,
        "content": content,
        "content_type": content_type,
        "id": message_id if message_id is not None else next(_ids),
    }
    if conversation_id is not None:
        payload["conversation"] = {"id": conversation_id}
    if sender_phone is not None:
        payload["sender"] = {"phone_number": sender_phone, "name": sender_name}
    return payload


def _body(event: dict[str, Any]) -> bytes:
    return json.dumps(event, separators=(",", ":")).encode("utf-8")


def _make_app(monkeypatch: Any) -> Any:
    """Create a Flask app with Chatwoot wired and synchronous background work."""
    proxy, flask_app = make_app_modules()

    monkeypatch.setattr(chatwoot_signature, "CHATWOOT_WEBHOOK_SECRET", SECRET)

    # Run background processing inline so assertions can observe state.
    def _run_inline(event: Any) -> Any:
        message_processor.process_chatwoot_message(event)

    monkeypatch.setattr(chatwoot_routes, "_run_in_background", _run_inline)
    return proxy, flask_app


# ─── Route-level assertions ────────────────────────────────────────


def test_route_rejects_invalid_signature(monkeypatch: Any) -> None:
    _, flask_app = _make_app(monkeypatch)
    body = _body(_event())
    response = flask_app.test_client().post(
        "/chatwoot-webhook",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Chatwoot-Signature": "deadbeef",
        },
    )
    assert response.status_code == 401


def test_route_rejects_missing_signature(monkeypatch: Any) -> None:
    _, flask_app = _make_app(monkeypatch)
    body = _body(_event())
    response = flask_app.test_client().post(
        "/chatwoot-webhook",
        data=body,
        content_type="application/json",
    )
    assert response.status_code == 401


def test_route_ignores_outgoing_message(monkeypatch: Any) -> None:
    _, flask_app = _make_app(monkeypatch)
    body = _body(_event(message_type="outgoing"))
    response = flask_app.test_client().post(
        "/chatwoot-webhook",
        data=body,
        headers=_headers(body),
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "ignored"


def test_route_ignores_private_note(monkeypatch: Any) -> None:
    _, flask_app = _make_app(monkeypatch)
    body = _body(_event(private=True))
    response = flask_app.test_client().post(
        "/chatwoot-webhook",
        data=body,
        headers=_headers(body),
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "ignored"


def test_route_ignores_unknown_event(monkeypatch: Any) -> None:
    _, flask_app = _make_app(monkeypatch)
    body = _body(_event(event="conversation_updated"))
    response = flask_app.test_client().post(
        "/chatwoot-webhook",
        data=body,
        headers=_headers(body),
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "ignored"


def test_route_dispatches_incoming_message(monkeypatch: Any) -> None:
    proxy, flask_app = _make_app(monkeypatch)

    sent: list[tuple[int | str, str]] = []
    monkeypatch.setattr(
        message_processor.chatwoot_client,
        "send_message",
        lambda conv, text: sent.append((conv, text)),
    )
    monkeypatch.setattr(message_processor, "find_best_faq_match", lambda _: "FAQ ANSWER")
    proxy.allow_phone_message = lambda _phone: True
    proxy.seen_message = lambda _id: False

    body = _body(_event(content="What is botox?", conversation_id=42))
    response = flask_app.test_client().post(
        "/chatwoot-webhook",
        data=body,
        headers=_headers(body),
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
    assert sent and sent[0][0] == 42
    assert sent[0][1].startswith("FAQ ANSWER")


# ─── Processor-level assertions ────────────────────────────────────


@pytest.fixture()
def processor_env(monkeypatch: Any) -> Any:
    """Set up message_processor for direct unit tests against
    process_chatwoot_message without going through the Flask route."""
    proxy, _ = make_app_modules()
    proxy.allow_phone_message = lambda _phone: True
    proxy.seen_message = lambda _id: False

    sent: list[tuple[int | str, str]] = []
    notifications: list[str] = []
    monkeypatch.setattr(
        message_processor.chatwoot_client,
        "send_message",
        lambda conv, text: sent.append((conv, text)),
    )
    monkeypatch.setattr(
        message_processor.whatsapp_client,
        "notify_team",
        lambda message: notifications.append(message),
    )

    return {"proxy": proxy, "sent": sent, "notifications": notifications}


def test_processor_rejects_missing_conversation(processor_env: Any) -> None:
    event = _event(conversation_id=None)
    assert message_processor.process_chatwoot_message(event) == "invalid event"


def test_processor_rejects_unknown_sender(processor_env: Any) -> None:
    event = _event(sender_phone="!@#")  # too short and non-URL-safe
    assert message_processor.process_chatwoot_message(event) == "invalid sender"
    assert processor_env["sent"] == []


def test_processor_silences_opted_out_sender(processor_env: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(message_processor.inbox_service, "is_opted_out", lambda _phone: True)
    event = _event()
    assert message_processor.process_chatwoot_message(event) == "opted out"
    assert processor_env["sent"] == []


def test_processor_drops_rate_limited(processor_env: Any) -> None:
    processor_env["proxy"].allow_phone_message = lambda _phone: False
    event = _event()
    assert message_processor.process_chatwoot_message(event) == "rate limited"
    assert processor_env["sent"] == []


def test_processor_dedups_messages(processor_env: Any) -> None:
    seen: dict[Any, bool] = {}

    def _seen(message_id: Any) -> Any:
        return seen.setdefault(message_id, False)

    def _record(message_id: Any) -> Any:
        seen[message_id] = True

    def fake_seen_message(message_id: Any) -> Any:
        was_seen = seen.get(message_id, False)
        if not was_seen:
            seen[message_id] = True
        return was_seen

    processor_env["proxy"].seen_message = fake_seen_message

    event = _event(message_id=12345)
    first = message_processor.process_chatwoot_message(event)
    second = message_processor.process_chatwoot_message(event)
    assert first == "ok"
    assert second == "duplicate"


def test_processor_handles_human_handoff_keyword(processor_env: Any, monkeypatch: Any) -> None:
    event = _event(content="HUMAN")
    result = message_processor.process_chatwoot_message(event)
    assert result == "ok"
    assert processor_env["sent"]
    assert processor_env["notifications"]
    assert "HUMAN REQUESTED" in processor_env["notifications"][0]


def test_processor_records_opt_out_without_reply(processor_env: Any, monkeypatch: Any) -> None:
    recorded: dict[str, Any] = {}
    monkeypatch.setattr(
        message_processor,
        "is_opt_out_request",
        lambda _text: (True, "STOP", "en"),
    )
    monkeypatch.setattr(
        message_processor.inbox_service,
        "record_opt_out",
        lambda sender_id, **kwargs: recorded.update({"sender_id": sender_id, **kwargs}),
    )
    event = _event(content="STOP")
    result = message_processor.process_chatwoot_message(event)
    assert result == "opt out recorded"
    assert recorded["source"] == "chatwoot_keyword"
    assert recorded["keyword_used"] == "STOP"
    assert processor_env["sent"] == []


def test_processor_replies_with_faq_match(processor_env: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(message_processor, "find_best_faq_match", lambda _: "FAQ ANSWER")

    event = _event(content="What is botox?")
    result = message_processor.process_chatwoot_message(event)

    assert result == "ok"
    assert processor_env["sent"]
    conv_id, text = processor_env["sent"][0]
    assert conv_id == 42
    assert "FAQ ANSWER" in text


def test_processor_falls_back_to_ai(processor_env: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(message_processor, "find_best_faq_match", lambda _: None)
    monkeypatch.setattr(
        message_processor,
        "get_ai_response",
        lambda _text, _name: "AI ANSWER",
    )

    event = _event(content="something off-topic")
    result = message_processor.process_chatwoot_message(event)

    assert result == "ok"
    text = processor_env["sent"][0][1]
    assert "AI ANSWER" in text


def test_processor_too_long_message(processor_env: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(message_processor, "MAX_INCOMING_TEXT_CHARS", 16)
    event = _event(content="x" * 100)
    result = message_processor.process_chatwoot_message(event)
    assert result == "ok"
    text = processor_env["sent"][0][1]
    assert "too long" in text.lower()


def test_processor_treats_non_text_as_media(processor_env: Any, monkeypatch: Any) -> None:
    event = _event(content="", content_type="incoming_image")
    result = message_processor.process_chatwoot_message(event)
    assert result == "ok"
    assert processor_env["sent"]


# ─── Configuration validation ─────────────────────────────────────


def test_misconfiguration_when_transport_off_returns_none() -> None:
    assert message_processor.chatwoot_transport_misconfiguration() is None


def test_misconfiguration_when_transport_on_and_missing_vars(monkeypatch: Any) -> None:
    monkeypatch.setattr(message_processor, "CHATWOOT_TRANSPORT", True)
    monkeypatch.setattr(message_processor, "CHATWOOT_API_TOKEN", "")
    monkeypatch.setattr(message_processor, "CHATWOOT_ACCOUNT_ID", "")
    monkeypatch.setattr(message_processor, "CHATWOOT_WEBHOOK_SECRET", "")

    error = message_processor.chatwoot_transport_misconfiguration()
    assert error is not None
    assert "CHATWOOT_API_TOKEN" in error
    assert "CHATWOOT_ACCOUNT_ID" in error
    assert "CHATWOOT_WEBHOOK_SECRET" in error


def test_misconfiguration_passes_when_fully_configured(monkeypatch: Any) -> None:
    monkeypatch.setattr(message_processor, "CHATWOOT_TRANSPORT", True)
    monkeypatch.setattr(message_processor, "CHATWOOT_API_TOKEN", "tok")
    monkeypatch.setattr(message_processor, "CHATWOOT_ACCOUNT_ID", "164322")
    monkeypatch.setattr(message_processor, "CHATWOOT_WEBHOOK_SECRET", "secret")
    assert message_processor.chatwoot_transport_misconfiguration() is None
