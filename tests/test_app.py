from __future__ import annotations

from types import SimpleNamespace

import requests

from tests.support import make_app_modules


def _make_app(monkeypatch=None):
    """Build a fresh Flask app for one test via the application factory.

    Returns (app_module, flask_app). Module-level monkeypatches go on
    app_module; HTTP requests go through flask_app.test_client().
    """
    app_module, flask_app = make_app_modules()

    if monkeypatch is not None:
        monkeypatch.setattr(app_module, "verify_meta_signature", lambda: True)
        monkeypatch.setattr(app_module, "allow_phone_message", lambda _phone: True)
        monkeypatch.setattr(app_module, "TEAM_NOTIFY_PHONE", "")

    return app_module, flask_app


def test_root_and_health_routes(content_file):
    app_module, flask_app = _make_app()
    client = flask_app.test_client()

    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200


def test_webhook_verify_success(content_file, monkeypatch):
    app_module, flask_app = _make_app()
    monkeypatch.setattr(app_module, "VERIFY_TOKEN", "test-token")
    client = flask_app.test_client()

    response = client.get(
        "/webhook?hub.mode=subscribe&hub.verify_token=test-token&hub.challenge=12345"
    )

    assert response.status_code == 200
    assert response.data.decode() == "12345"


def test_webhook_verify_forbidden(content_file, monkeypatch):
    app_module, flask_app = _make_app()
    monkeypatch.setattr(app_module, "VERIFY_TOKEN", "test-token")
    client = flask_app.test_client()

    assert client.get("/webhook").status_code == 403
    assert (
        client.get(
            "/webhook?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=12345"
        ).status_code
        == 403
    )


def test_post_non_json_returns_415(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    client = flask_app.test_client()

    response = client.post("/webhook", data="not json", content_type="text/plain")

    assert response.status_code == 415
    assert response.get_json()["status"] == "unsupported content type"


def test_post_empty_json_returns_400(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    client = flask_app.test_client()

    response = client.post("/webhook", json={})

    assert response.status_code == 400
    assert response.get_json()["status"] == "no data"


def test_post_status_update_returns_no_messages(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    client = flask_app.test_client()

    response = client.post(
        "/webhook", json={"entry": [{"changes": [{"value": {"statuses": [{"id": "1"}]}}]}]}
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "no messages"


def test_post_invalid_webhook_schema_returns_400(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    client = flask_app.test_client()

    response = client.post(
        "/webhook", json={"entry": [{"changes": [{"value": {"messages": "bad"}}]}]}
    )

    assert response.status_code == 400
    assert response.get_json()["status"] == "invalid payload"


def test_text_message_uses_faq_and_sends_response(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    sent = []

    def fake_send(to_phone, text):
        sent.append((to_phone, text))
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(app_module, "send_whatsapp_message", fake_send)

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
                                    {"from": "37368826828", "type": "text", "text": {"body": "hi"}}
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


def test_text_message_falls_back_to_ai(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    sent = []

    monkeypatch.setattr(app_module, "find_best_faq_match", lambda text: None)
    monkeypatch.setattr(app_module, "get_ai_response", lambda text, sender_name="": "AI answer")
    monkeypatch.setattr(
        app_module, "send_whatsapp_message", lambda to_phone, text: sent.append((to_phone, text))
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
                                        "from": "37368826828",
                                        "type": "text",
                                        "text": {"body": "unknown question"},
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
    assert sent == [
        (
            "37368826828",
            "AI answer\n\n_This is an automated assistant. Reply HUMAN to speak with our team._",
        )
    ]


def test_human_handoff_does_not_double_reply(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    sent = []

    monkeypatch.setattr(
        app_module, "send_whatsapp_message", lambda to_phone, text: sent.append((to_phone, text))
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
                                        "from": "37368826828",
                                        "type": "text",
                                        "text": {"body": "HUMAN"},
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
    assert sent == [("37368826828", "Human EN: A team member will get back to you.")]


def test_media_message_uses_media_response(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    sent = []

    monkeypatch.setattr(
        app_module, "send_whatsapp_message", lambda to_phone, text: sent.append((to_phone, text))
    )

    client = flask_app.test_client()
    response = client.post(
        "/webhook",
        json={
            "entry": [
                {"changes": [{"value": {"messages": [{"from": "37368826828", "type": "image"}]}}]}
            ]
        },
    )

    assert response.status_code == 200
    assert sent == [("37368826828", "Media EN: A team member will review it shortly.")]


def test_unknown_message_type_uses_unknown_response(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)
    sent = []

    monkeypatch.setattr(
        app_module, "send_whatsapp_message", lambda to_phone, text: sent.append((to_phone, text))
    )

    client = flask_app.test_client()
    response = client.post(
        "/webhook",
        json={
            "entry": [
                {"changes": [{"value": {"messages": [{"from": "37368826828", "type": "sticker"}]}}]}
            ]
        },
    )

    assert response.status_code == 200
    assert sent == [("37368826828", "Unknown EN: Please send us a text message.")]


def test_processing_exception_returns_200(content_file, monkeypatch):
    app_module, flask_app = _make_app(monkeypatch)

    def fail(_text):
        raise RuntimeError("boom")

    monkeypatch.setattr(app_module, "find_best_faq_match", fail)

    client = flask_app.test_client()
    response = client.post(
        "/webhook",
        json={
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {"from": "37368826828", "type": "text", "text": {"body": "hi"}}
                                ]
                            }
                        }
                    ]
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_send_whatsapp_message_missing_config(content_file, monkeypatch):
    app_module, flask_app = _make_app()

    monkeypatch.setattr(app_module, "WHATSAPP_TOKEN", "")
    monkeypatch.setattr(app_module, "WHATSAPP_PHONE_NUMBER_ID", "123")

    assert app_module.send_whatsapp_message("37368826828", "hello") is None

    monkeypatch.setattr(app_module, "WHATSAPP_TOKEN", "token")
    monkeypatch.setattr(app_module, "WHATSAPP_PHONE_NUMBER_ID", "")

    assert app_module.send_whatsapp_message("37368826828", "hello") is None


def test_send_whatsapp_message_success(content_file, monkeypatch):
    app_module, flask_app = _make_app()

    def fake_post(url, headers, json, timeout):
        assert "v21.0" in url
        assert headers["Authorization"] == "Bearer token"
        assert json["to"] == "37368826828"
        return SimpleNamespace(status_code=200, text="ok")

    monkeypatch.setattr(app_module, "WHATSAPP_TOKEN", "token")
    monkeypatch.setattr(app_module, "WHATSAPP_PHONE_NUMBER_ID", "111")
    monkeypatch.setattr(app_module, "GRAPH_API_VERSION", "v21.0")
    monkeypatch.setattr(app_module.requests, "post", fake_post)

    response = app_module.send_whatsapp_message("37368826828", "hello")

    assert response.status_code == 200


def test_send_whatsapp_message_failure_status(content_file, monkeypatch):
    app_module, flask_app = _make_app()

    def fake_post(url, headers, json, timeout):
        assert "111/messages" in url
        assert headers["Authorization"] == "Bearer token"
        assert json["to"] == "37368826828"
        assert timeout == 20
        return SimpleNamespace(status_code=401, text="bad token")

    monkeypatch.setattr(app_module, "WHATSAPP_TOKEN", "token")
    monkeypatch.setattr(app_module, "WHATSAPP_PHONE_NUMBER_ID", "111")
    monkeypatch.setattr(app_module.requests, "post", fake_post)

    response = app_module.send_whatsapp_message("37368826828", "hello")

    assert response.status_code == 401


def test_send_whatsapp_message_request_exception(content_file, monkeypatch):
    app_module, flask_app = _make_app()

    def fake_post(*args, **kwargs):
        raise requests.Timeout("timeout")

    monkeypatch.setattr(app_module, "WHATSAPP_TOKEN", "token")
    monkeypatch.setattr(app_module, "WHATSAPP_PHONE_NUMBER_ID", "111")
    monkeypatch.setattr(app_module.requests, "post", fake_post)

    assert app_module.send_whatsapp_message("37368826828", "hello") is None
