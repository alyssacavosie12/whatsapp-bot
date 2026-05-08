from __future__ import annotations

import time
from datetime import UTC, datetime

from werkzeug.security import generate_password_hash

from inbox.store import InboxMessage
from tests.support import make_app_modules


def _make_app(monkeypatch=None):
    """Build a fresh Flask app for one test via the application factory.

    Returns (app_module, flask_app); module-level monkeypatches go on
    app_module, HTTP requests through flask_app.test_client().
    """
    app_module, flask_app = make_app_modules()

    if monkeypatch is not None:
        monkeypatch.setattr(app_module, "verify_meta_signature", lambda: True)
        monkeypatch.setattr(app_module, "allow_phone_message", lambda _phone: True)
        monkeypatch.setattr(app_module, "TEAM_NOTIFY_PHONE", "")
        monkeypatch.setattr(app_module, "record_opt_in_proof", lambda *_args, **_kwargs: None)

    return app_module, flask_app


def _configure_admin(app_module, monkeypatch):
    monkeypatch.setattr(app_module, "INBOX_ENABLED", True)
    monkeypatch.setattr(app_module, "INBOX_DATABASE_URL", "postgresql://inbox")
    monkeypatch.setattr(app_module, "INBOX_ENCRYPTION_KEY", "configured-key")
    monkeypatch.setattr(app_module, "INBOX_REQUIRE_ENCRYPTION", True)
    monkeypatch.setattr(app_module, "INBOX_ADMIN_USERNAME", "owner")
    monkeypatch.setattr(
        app_module,
        "INBOX_ADMIN_PASSWORD_HASH",
        generate_password_hash("secret"),
    )
    monkeypatch.setattr(app_module, "INBOX_VIEWER_USERNAME", "viewer")
    monkeypatch.setattr(
        app_module,
        "INBOX_VIEWER_PASSWORD_HASH",
        generate_password_hash("view"),
    )
    monkeypatch.setattr(app_module, "META_APP_SECRET", "csrf-secret")


def _login_session(client, *, username: str = "owner", role: str = "admin") -> None:
    """Mark the Flask test client as logged in to the admin panel."""
    with client.session_transaction() as sess:
        sess["admin_authenticated"] = True
        sess["inbox_username"] = username
        sess["inbox_role"] = role
        sess["inbox_last_seen_at"] = int(time.time())


def _set_login_csrf(client, token: str) -> str:
    """Install a login CSRF token in the test session."""
    with client.session_transaction() as sess:
        sess["inbox_login_csrf_token"] = token

    return token


def _message(message_id: int = 1) -> InboxMessage:
    return InboxMessage(
        id=message_id,
        whatsapp_message_id=f"wamid.{message_id}",
        direction="incoming",
        sender_phone="37368826828",
        sender_phone_masked="***6828",
        sender_name="Test User",
        message_type="text",
        body="Need an appointment",
        body_encrypted=True,
        body_length=19,
        created_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        deleted_at=None,
        deleted_by="",
    )


def test_incoming_message_is_stored_when_inbox_is_configured(
    content_file,
    monkeypatch,
):
    app_module, flask_app = _make_app(monkeypatch)

    stored = []
    proofs = []
    sent = []

    monkeypatch.setattr(app_module, "INBOX_ENABLED", True)
    monkeypatch.setattr(app_module, "INBOX_DATABASE_URL", "postgresql://inbox")
    monkeypatch.setattr(app_module, "INBOX_ENCRYPTION_KEY", "test-key")
    monkeypatch.setattr(app_module, "INBOX_PROOF_SECRET", "proof-secret")
    monkeypatch.setattr(app_module, "INBOX_RETENTION_DAYS", 14)
    monkeypatch.setattr(
        app_module,
        "send_whatsapp_message",
        lambda to, text: sent.append((to, text)),
    )

    def fake_record(database_url, **kwargs):
        stored.append((database_url, kwargs))

    monkeypatch.setattr(app_module, "record_incoming_message", fake_record)
    monkeypatch.setattr(
        app_module,
        "record_opt_in_proof",
        lambda database_url, **kwargs: proofs.append((database_url, kwargs)),
    )

    client = flask_app.test_client()
    response = client.post(
        "/webhook",
        json={
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "contacts": [{"profile": {"name": "Test User"}}],
                                "messages": [
                                    {
                                        "id": "wamid.inbox.1",
                                        "from": "37368826828",
                                        "type": "text",
                                        "text": {"body": "hi"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        },
    )

    assert response.status_code == 200
    assert stored == [
        (
            "postgresql://inbox",
            {
                "whatsapp_message_id": "wamid.inbox.1",
                "sender_phone": "37368826828",
                "sender_phone_masked": "***6828",
                "sender_name": "Test User",
                "message_type": "text",
                "body": "hi",
                "encryption_key": "test-key",
                "retention_days": 14,
            },
        )
    ]
    assert proofs[0][0] == "postgresql://inbox"
    assert proofs[0][1]["whatsapp_message_id"] == "wamid.inbox.1"
    assert proofs[0][1]["sender_phone"] == "37368826828"
    assert proofs[0][1]["proof_type"] == "inbound_customer_initiated"
    assert proofs[0][1]["proof_source"] == "whatsapp_webhook"
    assert proofs[0][1]["proof_secret"] == "proof-secret"
    assert sent == [("37368826828", "Hey there! Welcome to Tulum Botox.")]


def test_inbox_store_failure_does_not_block_webhook(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)

    sent = []

    monkeypatch.setattr(app_module, "INBOX_ENABLED", True)
    monkeypatch.setattr(app_module, "INBOX_DATABASE_URL", "postgresql://inbox")
    monkeypatch.setattr(app_module, "INBOX_ENCRYPTION_KEY", "test-key")
    monkeypatch.setattr(
        app_module,
        "send_whatsapp_message",
        lambda to, text: sent.append((to, text)),
    )

    def fail_record(*_args, **_kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(app_module, "record_incoming_message", fail_record)

    client = flask_app.test_client()
    response = client.post(
        "/webhook",
        json={
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "contacts": [{"profile": {"name": "Test User"}}],
                                "messages": [
                                    {
                                        "id": "wamid.inbox.2",
                                        "from": "37368826828",
                                        "type": "text",
                                        "text": {"body": "hi"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        },
    )

    assert response.status_code == 200
    assert sent == [("37368826828", "Hey there! Welcome to Tulum Botox.")]


def test_inbox_requires_encryption_key_when_configured(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)

    monkeypatch.setattr(app_module, "INBOX_ENABLED", True)
    monkeypatch.setattr(app_module, "INBOX_DATABASE_URL", "postgresql://inbox")
    monkeypatch.setattr(app_module, "INBOX_ENCRYPTION_KEY", "")
    monkeypatch.setattr(app_module, "INBOX_REQUIRE_ENCRYPTION", True)
    monkeypatch.setattr(app_module, "INBOX_ADMIN_USERNAME", "owner")
    monkeypatch.setattr(
        app_module,
        "INBOX_ADMIN_PASSWORD_HASH",
        generate_password_hash("secret"),
    )

    client = flask_app.test_client()
    response = client.get("/admin/messages")

    assert response.status_code == 503
    assert b"Inbox encryption is not configured" in response.data


def test_admin_login_is_rate_limited(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    _configure_admin(app_module, monkeypatch)

    monkeypatch.setattr(app_module, "is_inbox_auth_limited", lambda _keys: True)

    client = flask_app.test_client()
    token = _set_login_csrf(client, "test-login-csrf")

    response = client.post(
        "/admin/login",
        data={
            "username": "owner",
            "password": "wrong",
            "csrf_token": token,
        },
    )

    assert response.status_code == 429


def test_failed_admin_login_is_recorded(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    _configure_admin(app_module, monkeypatch)

    recorded = []

    monkeypatch.setattr(app_module, "is_inbox_auth_limited", lambda _keys: False)
    monkeypatch.setattr(
        app_module,
        "record_inbox_auth_failure",
        lambda keys: recorded.append(keys) or False,
    )

    client = flask_app.test_client()
    token = _set_login_csrf(client, "test-login-csrf")

    response = client.post(
        "/admin/login",
        data={
            "username": "owner",
            "password": "wrong",
            "csrf_token": token,
        },
    )

    assert response.status_code == 401
    assert recorded


def test_admin_messages_redirects_to_login(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    _configure_admin(app_module, monkeypatch)

    client = flask_app.test_client()
    response = client.get("/admin/messages")

    assert response.status_code == 303
    assert "/admin/login" in response.headers["Location"]


def test_admin_login_success_redirects_to_messages_and_audits(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    _configure_admin(app_module, monkeypatch)

    audits = []
    monkeypatch.setattr(
        app_module,
        "record_audit_event",
        lambda *args, **kwargs: audits.append((args, kwargs)),
    )

    client = flask_app.test_client()
    token = _set_login_csrf(client, "test-login-csrf")

    response = client.post(
        "/admin/login",
        data={
            "username": "owner",
            "password": "secret",
            "csrf_token": token,
            "next": "/admin/messages",
        },
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/admin/messages"
    assert audits[0][1]["actor"] == "owner"
    assert audits[0][1]["action"] == "login_success"


def test_admin_login_rejects_bad_csrf(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    _configure_admin(app_module, monkeypatch)

    client = flask_app.test_client()

    response = client.post(
        "/admin/login",
        data={
            "username": "owner",
            "password": "secret",
            "csrf_token": "wrong",
        },
    )

    assert response.status_code == 400
    assert b"Login form expired" in response.data


def test_admin_messages_renders_for_viewer_and_audits(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    _configure_admin(app_module, monkeypatch)

    audits = []

    monkeypatch.setattr(app_module, "list_inbox_messages", lambda *_args, **_kwargs: [_message()])
    monkeypatch.setattr(
        app_module,
        "record_audit_event",
        lambda *args, **kwargs: audits.append((args, kwargs)),
    )

    client = flask_app.test_client()
    _login_session(client, username="viewer", role="viewer")

    response = client.get("/admin/messages")

    assert response.status_code == 200
    assert b"Need an appointment" in response.data
    assert b"Delete" not in response.data
    assert response.headers["Cache-Control"] == "no-store"
    assert audits[0][1]["actor"] == "viewer"
    assert audits[0][1]["action"] == "view_messages"


def test_admin_message_detail_renders_for_viewer_and_audits(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    _configure_admin(app_module, monkeypatch)

    audits = []

    monkeypatch.setattr(app_module, "get_message_by_id", lambda *_args, **_kwargs: _message(42))
    monkeypatch.setattr(
        app_module,
        "record_audit_event",
        lambda *args, **kwargs: audits.append((args, kwargs)),
    )

    client = flask_app.test_client()
    _login_session(client, username="viewer", role="viewer")

    response = client.get("/admin/messages/42")

    assert response.status_code == 200
    assert b"Need an appointment" in response.data
    assert b"Delete message" not in response.data
    assert audits[0][1]["actor"] == "viewer"
    assert audits[0][1]["action"] == "view_message"
    assert audits[0][1]["target_message_id"] == 42


def test_admin_message_detail_shows_delete_for_admin(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    _configure_admin(app_module, monkeypatch)

    monkeypatch.setattr(app_module, "get_message_by_id", lambda *_args, **_kwargs: _message(42))

    client = flask_app.test_client()
    _login_session(client, username="owner", role="admin")

    response = client.get("/admin/messages/42")

    assert response.status_code == 200
    assert b"Delete message" in response.data


def test_admin_message_detail_returns_404_when_missing(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    _configure_admin(app_module, monkeypatch)

    monkeypatch.setattr(app_module, "get_message_by_id", lambda *_args, **_kwargs: None)

    client = flask_app.test_client()
    _login_session(client, username="owner", role="admin")

    response = client.get("/admin/messages/404")

    assert response.status_code == 404
    assert b"Message not found" in response.data


def test_admin_can_soft_delete_message(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    _configure_admin(app_module, monkeypatch)

    deleted = []
    audits = []

    monkeypatch.setattr(
        app_module,
        "soft_delete_message",
        lambda *_args, **kwargs: deleted.append(kwargs) or True,
    )
    monkeypatch.setattr(
        app_module,
        "record_audit_event",
        lambda *args, **kwargs: audits.append((args, kwargs)),
    )

    token = app_module.inbox_csrf_token("owner", "delete", 42)

    client = flask_app.test_client()
    _login_session(client, username="owner", role="admin")

    response = client.post(
        "/admin/messages/42/delete",
        data={"csrf_token": token},
    )

    assert response.status_code == 303
    assert deleted == [{"message_id": 42, "deleted_by": "owner"}]
    assert audits[0][1]["actor"] == "owner"
    assert audits[0][1]["action"] == "delete_message"


def test_viewer_cannot_delete_message(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    _configure_admin(app_module, monkeypatch)

    token = app_module.inbox_csrf_token("viewer", "delete", 42)

    client = flask_app.test_client()
    _login_session(client, username="viewer", role="viewer")

    response = client.post(
        "/admin/messages/42/delete",
        data={"csrf_token": token},
    )

    assert response.status_code == 403


def test_admin_logout_clears_session(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    _configure_admin(app_module, monkeypatch)

    client = flask_app.test_client()
    _login_session(client, username="owner", role="admin")

    response = client.post("/admin/logout")

    assert response.status_code == 303
    assert "/admin/login" in response.headers["Location"]

    follow_up = client.get("/admin/messages")
    assert follow_up.status_code == 303
    assert "/admin/login" in follow_up.headers["Location"]


def test_all_messages_in_payload_are_processed(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)

    sent = []
    stored = []

    monkeypatch.setattr(app_module, "INBOX_ENABLED", True)
    monkeypatch.setattr(app_module, "INBOX_DATABASE_URL", "postgresql://inbox")
    monkeypatch.setattr(app_module, "INBOX_ENCRYPTION_KEY", "test-key")
    monkeypatch.setattr(
        app_module,
        "send_whatsapp_message",
        lambda to, text: sent.append((to, text)),
    )
    monkeypatch.setattr(
        app_module,
        "record_incoming_message",
        lambda _url, **kwargs: stored.append(kwargs),
    )

    client = flask_app.test_client()
    response = client.post(
        "/webhook",
        json={
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "contacts": [{"profile": {"name": "Test User"}}],
                                "messages": [
                                    {
                                        "id": "wamid.multi.1",
                                        "from": "37368826828",
                                        "type": "text",
                                        "text": {"body": "hi"},
                                    },
                                    {
                                        "id": "wamid.multi.2",
                                        "from": "37368826828",
                                        "type": "text",
                                        "text": {"body": "price"},
                                    },
                                ],
                            }
                        }
                    ]
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
    assert [item["whatsapp_message_id"] for item in stored] == [
        "wamid.multi.1",
        "wamid.multi.2",
    ]
    assert len(sent) == 2
