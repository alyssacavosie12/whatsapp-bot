from __future__ import annotations

from types import SimpleNamespace
from typing import Any


def test_no_anthropic_key_uses_fallback(content_file: Any, monkeypatch: Any) -> None:
    from bot import ai_responder

    monkeypatch.setattr(ai_responder, "ANTHROPIC_API_KEY", "")

    assert ai_responder.get_ai_response("hi").startswith("Human EN")


def test_no_anthropic_key_uses_spanish_fallback(content_file: Any, monkeypatch: Any) -> None:
    from bot import ai_responder

    monkeypatch.setattr(ai_responder, "ANTHROPIC_API_KEY", "")

    assert ai_responder.get_ai_response("hola").startswith("Human ES")


def test_empty_business_context_uses_fallback(content_file: Any, monkeypatch: Any) -> None:
    from bot import ai_responder

    monkeypatch.setattr(ai_responder, "ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.setattr(ai_responder, "get_business_context", lambda: "")

    assert ai_responder.get_ai_response("hi").startswith("Human EN")


def test_anthropic_success(content_file: Any, monkeypatch: Any) -> None:
    from bot import ai_responder

    class FakeMessages:
        def create(self, **kwargs: Any) -> Any:
            assert "Tulum BTX" in kwargs["system"]
            assert kwargs["messages"] == [
                {"role": "user", "content": "What services do you offer?"}
            ]
            return SimpleNamespace(content=[SimpleNamespace(text="We offer Dysport and fillers.")])

    class FakeClient:
        def __init__(self, api_key: Any, timeout: Any) -> None:
            assert api_key == "fake-key"
            assert timeout == ai_responder.ANTHROPIC_TIMEOUT_SECONDS
            self.messages = FakeMessages()

    monkeypatch.setattr(ai_responder, "ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.setattr(ai_responder.anthropic, "Anthropic", FakeClient)

    assert (
        ai_responder.get_ai_response("What services do you offer?")
        == "We offer Dysport and fillers."
    )


def test_anthropic_empty_response_uses_fallback(content_file: Any, monkeypatch: Any) -> None:
    from bot import ai_responder

    class FakeMessages:
        def create(self, **kwargs: Any) -> Any:
            return SimpleNamespace(content=[SimpleNamespace(text="")])

    class FakeClient:
        def __init__(self, api_key: Any, timeout: Any) -> None:
            self.messages = FakeMessages()

    monkeypatch.setattr(ai_responder, "ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.setattr(ai_responder.anthropic, "Anthropic", FakeClient)

    assert ai_responder.get_ai_response("hi").startswith("Human EN")


def test_anthropic_generic_exception_uses_fallback(content_file: Any, monkeypatch: Any) -> None:
    from bot import ai_responder

    class FakeMessages:
        def create(self, **kwargs: Any) -> Any:
            raise RuntimeError("network problem")

    class FakeClient:
        def __init__(self, api_key: Any, timeout: Any) -> None:
            self.messages = FakeMessages()

    monkeypatch.setattr(ai_responder, "ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.setattr(ai_responder.anthropic, "Anthropic", FakeClient)

    assert ai_responder.get_ai_response("hi").startswith("Human EN")


def test_anthropic_circuit_breaker_opens_after_failures(
    content_file: Any, monkeypatch: Any
) -> None:
    from bot import ai_responder
    from core.circuit_breaker import CircuitBreaker

    calls = []

    class FakeMessages:
        def create(self, **kwargs: Any) -> Any:
            calls.append(kwargs)
            raise RuntimeError("network problem")

    class FakeClient:
        def __init__(self, api_key: Any, timeout: Any) -> None:
            self.messages = FakeMessages()

    monkeypatch.setattr(ai_responder, "ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.setattr(ai_responder.anthropic, "Anthropic", FakeClient)
    monkeypatch.setattr(
        ai_responder,
        "ANTHROPIC_BREAKER",
        CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=60),
    )

    assert ai_responder.get_ai_response("hi").startswith("Human EN")
    assert ai_responder.anthropic_circuit_status() == "circuit_open"
    assert ai_responder.get_ai_response("hi again").startswith("Human EN")
    assert len(calls) == 1


def test_long_ai_response_is_truncated(content_file: Any, monkeypatch: Any) -> None:
    from bot import ai_responder

    class FakeMessages:
        def create(self, **kwargs: Any) -> Any:
            return SimpleNamespace(content=[SimpleNamespace(text="x" * 2000)])

    class FakeClient:
        def __init__(self, api_key: Any, timeout: Any) -> None:
            self.messages = FakeMessages()

    monkeypatch.setattr(ai_responder, "ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.setattr(ai_responder.anthropic, "Anthropic", FakeClient)

    response = ai_responder.get_ai_response("hi")

    assert len(response) == 1500
    assert response.endswith("...")
