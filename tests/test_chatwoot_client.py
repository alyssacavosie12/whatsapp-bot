"""Tests for bot.chatwoot_client.send_message."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from bot import chatwoot_client


def _response(status_code: int, body: Any = None) -> SimpleNamespace:
    """Return a minimal stand-in for requests.Response."""

    def _json() -> Any:
        if body is None:
            raise ValueError("no body")
        return body

    return SimpleNamespace(status_code=status_code, json=_json, text="")


@pytest.fixture()
def configured(monkeypatch: Any) -> Any:
    monkeypatch.setattr(chatwoot_client, "CHATWOOT_API_TOKEN", "tok")
    monkeypatch.setattr(chatwoot_client, "CHATWOOT_ACCOUNT_ID", "164322")
    monkeypatch.setattr(chatwoot_client, "CHATWOOT_BASE_URL", "https://chatwoot.example")
    monkeypatch.setattr(chatwoot_client, "CHATWOOT_REQUEST_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(chatwoot_client, "CHATWOOT_MAX_RETRIES", 3)
    monkeypatch.setattr(chatwoot_client, "CHATWOOT_RETRY_BACKOFF_SECONDS", 0)
    monkeypatch.setattr(chatwoot_client.time, "sleep", lambda _seconds: None)


def test_url_shape(configured: Any) -> None:
    assert (
        chatwoot_client.messages_url(42)
        == "https://chatwoot.example/api/v1/accounts/164322/conversations/42/messages"
    )


def test_returns_none_when_token_missing(monkeypatch: Any) -> None:
    monkeypatch.setattr(chatwoot_client, "CHATWOOT_API_TOKEN", "")
    monkeypatch.setattr(chatwoot_client, "CHATWOOT_ACCOUNT_ID", "164322")
    assert chatwoot_client.send_message(42, "hello") is None


def test_returns_none_when_account_missing(monkeypatch: Any) -> None:
    monkeypatch.setattr(chatwoot_client, "CHATWOOT_API_TOKEN", "tok")
    monkeypatch.setattr(chatwoot_client, "CHATWOOT_ACCOUNT_ID", "")
    assert chatwoot_client.send_message(42, "hello") is None


def test_returns_none_for_empty_text(configured: Any) -> None:
    assert chatwoot_client.send_message(42, "") is None


def test_returns_none_for_zero_conversation(configured: Any) -> None:
    assert chatwoot_client.send_message(0, "hello") is None


def test_request_shape_on_success(configured: Any, monkeypatch: Any) -> None:
    captured = MagicMock(return_value=_response(200, body={"id": 99}))
    monkeypatch.setattr(chatwoot_client.requests, "post", captured)

    response = chatwoot_client.send_message(42, "hello world")

    assert response is not None
    assert response.status_code == 200
    captured.assert_called_once()
    args, kwargs = captured.call_args
    assert args == ("https://chatwoot.example/api/v1/accounts/164322/conversations/42/messages",)
    assert kwargs["headers"]["api_access_token"] == "tok"
    assert kwargs["headers"]["Content-Type"] == "application/json"
    assert kwargs["json"] == {"content": "hello world", "message_type": "outgoing"}
    assert kwargs["timeout"] == 1.0


def test_201_treated_as_success(configured: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(
        chatwoot_client.requests,
        "post",
        MagicMock(return_value=_response(201, body={"id": 5})),
    )

    response = chatwoot_client.send_message(42, "hello")
    assert response is not None
    assert response.status_code == 201


def test_4xx_does_not_retry(configured: Any, monkeypatch: Any) -> None:
    post = MagicMock(return_value=_response(401, body={"error": "Unauthorized"}))
    monkeypatch.setattr(chatwoot_client.requests, "post", post)

    response = chatwoot_client.send_message(42, "hello")

    assert response is not None
    assert response.status_code == 401
    assert post.call_count == 1


def test_429_retries(configured: Any, monkeypatch: Any) -> None:
    responses = [
        _response(429, body={"error": "Throttle"}),
        _response(429, body={"error": "Throttle"}),
        _response(200, body={"id": 7}),
    ]
    post = MagicMock(side_effect=responses)
    monkeypatch.setattr(chatwoot_client.requests, "post", post)

    response = chatwoot_client.send_message(42, "hello")

    assert response is not None
    assert response.status_code == 200
    assert post.call_count == 3


def test_5xx_retries_then_succeeds(configured: Any, monkeypatch: Any) -> None:
    responses = [
        _response(503, body={"error": "Down"}),
        _response(200, body={"id": 8}),
    ]
    post = MagicMock(side_effect=responses)
    monkeypatch.setattr(chatwoot_client.requests, "post", post)

    response = chatwoot_client.send_message(42, "hello")
    assert response is not None
    assert response.status_code == 200
    assert post.call_count == 2


def test_retries_exhausted_returns_last_response(configured: Any, monkeypatch: Any) -> None:
    responses = [_response(503, body={"error": "Down"})] * 3
    post = MagicMock(side_effect=responses)
    monkeypatch.setattr(chatwoot_client.requests, "post", post)

    response = chatwoot_client.send_message(42, "hello")
    assert response is not None
    assert response.status_code == 503
    assert post.call_count == 3


def test_network_error_retries(configured: Any, monkeypatch: Any) -> None:
    post = MagicMock(
        side_effect=[
            requests.ConnectionError("boom"),
            _response(200, body={"id": 9}),
        ]
    )
    monkeypatch.setattr(chatwoot_client.requests, "post", post)

    response = chatwoot_client.send_message(42, "hello")
    assert response is not None
    assert response.status_code == 200
    assert post.call_count == 2


def test_network_error_persistent_returns_none(configured: Any, monkeypatch: Any) -> None:
    post = MagicMock(side_effect=requests.ConnectionError("boom"))
    monkeypatch.setattr(chatwoot_client.requests, "post", post)

    response = chatwoot_client.send_message(42, "hello")
    assert response is None
    assert post.call_count == 3
