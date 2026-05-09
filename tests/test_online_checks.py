from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any

import anthropic
import pytest
import requests
from dotenv import load_dotenv

PLACEHOLDER_HOST = "your-railway-service.up.railway.app"
ONLINE_ENV_FILE = Path(os.getenv("ONLINE_CHECKS_ENV_FILE", ".env.online"))
if ONLINE_ENV_FILE.exists():
    load_dotenv(ONLINE_ENV_FILE, override=False)
load_dotenv(override=False)


def _flag(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _timeout() -> float:
    raw_value = os.getenv("ONLINE_TEST_TIMEOUT_SECONDS", "10")
    try:
        return max(1.0, float(raw_value))
    except ValueError:
        return 10.0


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        pytest.fail(f"{name} is required for online checks", pytrace=False)

    return value


def _base_url() -> str:
    value = _required_env("PUBLIC_BASE_URL").rstrip("/")
    if PLACEHOLDER_HOST in value:
        pytest.fail(
            "PUBLIC_BASE_URL still contains the placeholder Railway domain",
            pytrace=False,
        )

    return value


def _url(path: str) -> str:
    return f"{_base_url()}{path}"


def _safe_response(response: requests.Response) -> str:
    return f"status={response.status_code} body={response.text[:400]}"


def _request(method: str, url: str, **kwargs: Any) -> requests.Response:
    try:
        return requests.request(method, url, timeout=_timeout(), **kwargs)
    except requests.RequestException as exc:
        pytest.fail(
            f"request failed url={url} error={exc.__class__.__name__}: {exc}",
            pytrace=False,
        )


def _signed_webhook_body(payload: dict[str, Any], app_secret: str) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return body, {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": f"sha256={digest}",
    }


pytestmark = [
    pytest.mark.online,
    pytest.mark.skipif(
        not _flag("RUN_ONLINE_CHECKS"),
        reason="set RUN_ONLINE_CHECKS=true and fill .env.online to run live checks",
    ),
]


def test_online_env_contract_is_safe_and_complete():
    required = [
        "PUBLIC_BASE_URL",
        "WHATSAPP_TOKEN",
        "WHATSAPP_PHONE_NUMBER_ID",
        "VERIFY_TOKEN",
        "META_APP_SECRET",
        "ANTHROPIC_API_KEY",
        "FLASK_SECRET_KEY",
        "INBOX_ENCRYPTION_KEY",
        "INBOX_CSRF_SECRET",
        "INBOX_PROOF_SECRET",
    ]
    missing = [name for name in required if not os.getenv(name, "").strip()]
    assert missing == []

    assert _base_url().startswith("https://")
    assert os.getenv("ALLOW_UNSIGNED_WEBHOOKS", "false").strip().lower() == "false"
    assert os.getenv("LOG_INCOMING_MESSAGES", "false").strip().lower() == "false"
    assert os.getenv("INBOX_REQUIRE_ENCRYPTION", "true").strip().lower() == "true"
    assert os.getenv("DATABASE_URL") or os.getenv("DATABASE_PRIVATE_URL")


def test_public_health_endpoint_is_reachable():
    response = _request("GET", _url("/health"))
    payload = response.json()

    if _flag("ONLINE_REQUIRE_HEALTH_OK", default=True):
        assert response.status_code == 200, _safe_response(response)
        assert payload["status"] == "ok"
        assert payload["components"]["postgres"] in {"ok", "disabled"}
        assert payload["components"]["redis"] in {"ok", "disabled"}
        assert payload["components"]["anthropic"] == "ok"
    else:
        assert response.status_code in {200, 503}, _safe_response(response)
        assert payload["status"] in {"ok", "degraded"}


def test_public_privacy_notice_is_reachable():
    response = _request("GET", _url("/privacy"))

    assert response.status_code == 200, _safe_response(response)
    assert "Privacy Notice" in response.text
    assert "Subprocessors" in response.text
    assert "Anthropic PBC" in response.text


def test_webhook_verify_token_matches_deployed_env():
    challenge = "online-check-challenge"
    response = _request(
        "GET",
        _url("/webhook"),
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": _required_env("VERIFY_TOKEN"),
            "hub.challenge": challenge,
        },
    )

    assert response.status_code == 200, _safe_response(response)
    assert response.text == challenge


def test_unsigned_webhook_post_is_rejected():
    response = _request(
        "POST",
        _url("/webhook"),
        json={"entry": [{"changes": [{"value": {"statuses": [{"id": "unsigned"}]}}]}]},
    )

    assert response.status_code == 401, _safe_response(response)


def test_signed_status_webhook_is_accepted_without_sending_messages():
    body, headers = _signed_webhook_body(
        {"entry": [{"changes": [{"value": {"statuses": [{"id": "online-check"}]}}]}]},
        _required_env("META_APP_SECRET"),
    )
    response = _request(
        "POST",
        _url("/webhook"),
        data=body,
        headers=headers,
    )

    assert response.status_code == 200, _safe_response(response)
    assert response.json()["status"] in {"no messages", "ok"}


def test_meta_graph_token_can_read_configured_phone_number():
    version = os.getenv("GRAPH_API_VERSION", "v23.0").strip() or "v23.0"
    phone_number_id = _required_env("WHATSAPP_PHONE_NUMBER_ID")
    response = _request(
        "GET",
        f"https://graph.facebook.com/{version}/{phone_number_id}",
        params={"fields": "id,display_phone_number,verified_name"},
        headers={"Authorization": f"Bearer {_required_env('WHATSAPP_TOKEN')}"},
    )

    assert response.status_code == 200, _safe_response(response)
    assert str(response.json()["id"]) == phone_number_id


def test_anthropic_api_key_can_list_models():
    client = anthropic.Anthropic(
        api_key=_required_env("ANTHROPIC_API_KEY"),
        timeout=_timeout(),
    )
    try:
        models = client.models.list(limit=1)
    except anthropic.AnthropicError as exc:
        pytest.fail(f"Anthropic request failed: {exc.__class__.__name__}", pytrace=False)

    assert len(models.data) >= 1


@pytest.mark.skipif(
    not _flag("ONLINE_CHECK_DATABASE"),
    reason="set ONLINE_CHECK_DATABASE=true when Postgres is reachable from this runner",
)
def test_postgres_url_accepts_connections():
    import psycopg

    database_url = (
        os.getenv("DATABASE_URL", "").strip() or os.getenv("DATABASE_PRIVATE_URL", "").strip()
    )
    sslmode = os.getenv("ONLINE_DATABASE_SSLMODE", "require").strip() or "require"

    with psycopg.connect(
        database_url,
        connect_timeout=int(_timeout()),
        sslmode=sslmode,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone()[0] == 1


@pytest.mark.skipif(
    not _flag("ONLINE_CHECK_REDIS"),
    reason="set ONLINE_CHECK_REDIS=true when Redis is reachable from this runner",
)
def test_redis_url_accepts_connections():
    import redis

    client = redis.from_url(
        _required_env("REDIS_URL"),
        socket_connect_timeout=_timeout(),
        socket_timeout=_timeout(),
    )

    assert client.ping() is True


@pytest.mark.skipif(
    not _flag("ONLINE_CHECK_ADMIN"),
    reason="set ONLINE_CHECK_ADMIN=true and provide ONLINE_INBOX_USERNAME/PASSWORD",
)
def test_admin_inbox_basic_auth_works():
    response = _request(
        "GET",
        _url("/admin/messages?limit=1"),
        auth=(
            _required_env("ONLINE_INBOX_USERNAME"),
            _required_env("ONLINE_INBOX_PASSWORD"),
        ),
    )

    assert response.status_code == 200, _safe_response(response)
    assert "Messages Inbox" in response.text
