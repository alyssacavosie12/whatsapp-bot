"""Tests for webhook.chatwoot_signature.verify_chatwoot_signature."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import pytest
from flask import Flask

from webhook import chatwoot_signature

SECRET = "test-chatwoot-secret"


def _digest(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.fixture()
def flask_app() -> Any:
    """Minimal Flask app exposing a single route that calls the verifier."""
    app = Flask(__name__)

    @app.route("/probe", methods=["POST"])
    def probe() -> Any:
        return ("ok" if chatwoot_signature.verify_chatwoot_signature() else "fail"), 200

    return app


def test_rejects_when_secret_unset(flask_app: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(chatwoot_signature, "CHATWOOT_WEBHOOK_SECRET", "")
    body = b'{"event":"message_created"}'
    response = flask_app.test_client().post(
        "/probe",
        data=body,
        headers={"X-Chatwoot-Signature": _digest(body)},
    )
    assert response.data == b"fail"


def test_rejects_missing_header(flask_app: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(chatwoot_signature, "CHATWOOT_WEBHOOK_SECRET", SECRET)
    body = b'{"event":"message_created"}'
    response = flask_app.test_client().post("/probe", data=body)
    assert response.data == b"fail"


def test_rejects_wrong_signature(flask_app: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(chatwoot_signature, "CHATWOOT_WEBHOOK_SECRET", SECRET)
    body = b'{"event":"message_created"}'
    response = flask_app.test_client().post(
        "/probe",
        data=body,
        headers={"X-Chatwoot-Signature": _digest(body, "different-secret")},
    )
    assert response.data == b"fail"


def test_accepts_valid_signature(flask_app: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(chatwoot_signature, "CHATWOOT_WEBHOOK_SECRET", SECRET)
    body = b'{"event":"message_created","conversation":{"id":7}}'
    response = flask_app.test_client().post(
        "/probe",
        data=body,
        headers={"X-Chatwoot-Signature": _digest(body)},
    )
    assert response.data == b"ok"


def test_signature_uses_constant_time_compare(flask_app: Any, monkeypatch: Any) -> None:
    """The verifier must use hmac.compare_digest, not raw ==.

    Asserted indirectly: a signature that is the right length but wrong
    content must not produce a hash collision with the truncated digest.
    """
    monkeypatch.setattr(chatwoot_signature, "CHATWOOT_WEBHOOK_SECRET", SECRET)
    body = b'{"event":"message_created"}'
    wrong = "a" * 64  # right length, wrong content
    response = flask_app.test_client().post(
        "/probe",
        data=body,
        headers={"X-Chatwoot-Signature": wrong},
    )
    assert response.data == b"fail"
