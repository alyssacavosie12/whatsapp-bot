"""Environment configuration for the WhatsApp bot."""

from __future__ import annotations

import os
from typing import Final

from dotenv import load_dotenv

load_dotenv()


# ─── Env parsing helpers ─────────────────────────────────────


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default

    try:
        return float(value)
    except ValueError:
        return default


# ─── WhatsApp / Meta ─────────────────────────────────────────

WHATSAPP_TOKEN: Final = os.getenv("WHATSAPP_TOKEN", "").strip()
WHATSAPP_PHONE_NUMBER_ID: Final = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
VERIFY_TOKEN: Final = os.getenv("VERIFY_TOKEN", "tulum-btx-bot-token").strip()
GRAPH_API_VERSION: Final = os.getenv("GRAPH_API_VERSION", "v23.0").strip()

META_APP_SECRET: Final = os.getenv("META_APP_SECRET", "").strip()
# Retained for older Railway configs; app.py now refuses unsigned POST webhooks.
ALLOW_UNSIGNED_WEBHOOKS: Final = _env_bool("ALLOW_UNSIGNED_WEBHOOKS", default=False)
MAX_CONTENT_LENGTH: Final = _env_int("MAX_CONTENT_LENGTH", 65536)
MAX_INCOMING_TEXT_CHARS: Final = _env_int("MAX_INCOMING_TEXT_CHARS", 4000)
LOG_INCOMING_MESSAGES: Final = _env_bool("LOG_INCOMING_MESSAGES", default=False)
INCOMING_MESSAGE_LOG_MAX_CHARS: Final = _env_int("INCOMING_MESSAGE_LOG_MAX_CHARS", 1000)


# ─── Flask / HTTP hardening ──────────────────────────────────

FLASK_SECRET_KEY: Final = os.getenv("FLASK_SECRET_KEY", "").strip()
FORCE_HTTPS: Final = _env_bool("FORCE_HTTPS", default=False)


# ─── Dedup ───────────────────────────────────────────────────

REDIS_URL: Final = os.getenv("REDIS_URL", "").strip()
REDIS_MAX_CONNECTIONS: Final = _env_int("REDIS_MAX_CONNECTIONS", 20)
REDIS_SOCKET_TIMEOUT_SECONDS: Final = _env_float("REDIS_SOCKET_TIMEOUT_SECONDS", 3.0)
REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS: Final = _env_float(
    "REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS",
    2.0,
)
REDIS_HEALTH_CHECK_INTERVAL_SECONDS: Final = _env_int(
    "REDIS_HEALTH_CHECK_INTERVAL_SECONDS",
    30,
)
MESSAGE_TTL_SECONDS: Final = _env_int("MESSAGE_TTL_SECONDS", 60 * 60)
MAX_LOCAL_DEDUP_SIZE: Final = _env_int("MAX_LOCAL_DEDUP_SIZE", 10_000)


# ─── Rate limiting ───────────────────────────────────────────

PHONE_RATE_LIMIT_MAX_MESSAGES: Final = _env_int("PHONE_RATE_LIMIT_MAX_MESSAGES", 20)
PHONE_RATE_LIMIT_WINDOW_SECONDS: Final = _env_int("PHONE_RATE_LIMIT_WINDOW_SECONDS", 60)
WEBHOOK_RATE_LIMIT: Final = os.getenv("WEBHOOK_RATE_LIMIT", "300 per minute").strip()
RATE_LIMIT_STORAGE_URL: Final = os.getenv("RATE_LIMIT_STORAGE_URL", REDIS_URL).strip()


# ─── Anthropic ───────────────────────────────────────────────

ANTHROPIC_API_KEY: Final = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL: Final = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip()
ANTHROPIC_MAX_TOKENS: Final = _env_int("ANTHROPIC_MAX_TOKENS", 300)
ANTHROPIC_TIMEOUT_SECONDS: Final = _env_int("ANTHROPIC_TIMEOUT_SECONDS", 30)
ANTHROPIC_CIRCUIT_FAILURE_THRESHOLD: Final = _env_int(
    "ANTHROPIC_CIRCUIT_FAILURE_THRESHOLD",
    5,
)
ANTHROPIC_CIRCUIT_RECOVERY_SECONDS: Final = _env_int(
    "ANTHROPIC_CIRCUIT_RECOVERY_SECONDS",
    60,
)


# ─── Bot behavior ────────────────────────────────────────────

BOT_DISCLOSURE: Final = _env_bool("BOT_DISCLOSURE", default=True)
TEAM_NOTIFY_PHONE: Final = os.getenv("TEAM_NOTIFY_PHONE", "").strip()
PRIVACY_NOTICE_URL: Final = os.getenv(
    "PRIVACY_NOTICE_URL",
    "https://www.tulumbotox.com/privacy",
).strip()
PRIVACY_RESPONSIBLE_NAME: Final = os.getenv(
    "PRIVACY_RESPONSIBLE_NAME",
    "Tulum Botox (Tulum BTX)",
).strip()
PRIVACY_RESPONSIBLE_ADDRESS: Final = os.getenv(
    "PRIVACY_RESPONSIBLE_ADDRESS",
    "Tulum Centro, Tulum, Quintana Roo, Mexico",
).strip()
PRIVACY_CONTACT_EMAIL: Final = os.getenv(
    "PRIVACY_CONTACT_EMAIL",
    "Ally@TulumBotox.com",
).strip()
PRIVACY_CONTACT_PHONE: Final = os.getenv(
    "PRIVACY_CONTACT_PHONE",
    "+52 984 105 0808",
).strip()
PRIVACY_NOTICE_LAST_UPDATED: Final = os.getenv(
    "PRIVACY_NOTICE_LAST_UPDATED",
    "2026-05-08",
).strip()
WHATSAPP_MAX_RETRIES: Final = _env_int("WHATSAPP_MAX_RETRIES", 3)
WHATSAPP_RETRY_BACKOFF_SECONDS: Final = _env_float("WHATSAPP_RETRY_BACKOFF_SECONDS", 1.0)
WHATSAPP_REQUEST_TIMEOUT_SECONDS: Final = _env_float("WHATSAPP_REQUEST_TIMEOUT_SECONDS", 10.0)


# ─── Admin inbox ──────────────────────────────────────────────

INBOX_ENABLED: Final = _env_bool("INBOX_ENABLED", default=True)
INBOX_DATABASE_URL: Final = (
    os.getenv("DATABASE_PRIVATE_URL", "").strip()
    or os.getenv(
        "DATABASE_URL",
        "",
    ).strip()
)
DATABASE_POOL_MIN_SIZE: Final = _env_int("DATABASE_POOL_MIN_SIZE", 2)
DATABASE_POOL_MAX_SIZE: Final = _env_int("DATABASE_POOL_MAX_SIZE", 10)
DATABASE_POOL_TIMEOUT_SECONDS: Final = _env_float("DATABASE_POOL_TIMEOUT_SECONDS", 5.0)
DATABASE_POOL_MAX_WAITING: Final = _env_int("DATABASE_POOL_MAX_WAITING", 20)
INBOX_RETENTION_DAYS: Final = _env_int("INBOX_RETENTION_DAYS", 30)
INBOX_REQUIRE_ENCRYPTION: Final = _env_bool("INBOX_REQUIRE_ENCRYPTION", default=True)
INBOX_ENCRYPTION_KEY: Final = os.getenv("INBOX_ENCRYPTION_KEY", "").strip()
INBOX_CSRF_SECRET: Final = os.getenv("INBOX_CSRF_SECRET", "").strip()
INBOX_PROOF_SECRET: Final = os.getenv("INBOX_PROOF_SECRET", "").strip()
INBOX_AUTO_MIGRATE: Final = _env_bool("INBOX_AUTO_MIGRATE", default=True)
INBOX_AUTH_MAX_FAILED_ATTEMPTS: Final = _env_int("INBOX_AUTH_MAX_FAILED_ATTEMPTS", 5)
INBOX_AUTH_WINDOW_SECONDS: Final = _env_int("INBOX_AUTH_WINDOW_SECONDS", 15 * 60)
INBOX_SESSION_TIMEOUT_SECONDS: Final = _env_int("INBOX_SESSION_TIMEOUT_SECONDS", 30 * 60)

INBOX_ADMIN_USERNAME: Final = os.getenv("INBOX_ADMIN_USERNAME", "").strip()
INBOX_ADMIN_PASSWORD_HASH: Final = os.getenv("INBOX_ADMIN_PASSWORD_HASH", "").strip()
INBOX_VIEWER_USERNAME: Final = os.getenv("INBOX_VIEWER_USERNAME", "").strip()
INBOX_VIEWER_PASSWORD_HASH: Final = os.getenv("INBOX_VIEWER_PASSWORD_HASH", "").strip()


# ─── Chatwoot agent_bot integration ──────────────────────────
#
# When the bot operates as a Chatwoot agent_bot, Meta sends webhooks to
# Chatwoot, Chatwoot fires our /chatwoot-webhook on incoming messages, and
# replies go out via Chatwoot's REST API. CHATWOOT_TRANSPORT toggles which
# outbound transport the message processor uses.

CHATWOOT_TRANSPORT: Final = _env_bool("CHATWOOT_TRANSPORT", default=False)
CHATWOOT_BASE_URL: Final = (
    os.getenv("CHATWOOT_BASE_URL", "https://app.chatwoot.com").strip().rstrip("/")
)
CHATWOOT_ACCOUNT_ID: Final = os.getenv("CHATWOOT_ACCOUNT_ID", "").strip()
CHATWOOT_INBOX_ID: Final = os.getenv("CHATWOOT_INBOX_ID", "").strip()
CHATWOOT_API_TOKEN: Final = os.getenv("CHATWOOT_API_TOKEN", "").strip()
CHATWOOT_WEBHOOK_SECRET: Final = os.getenv("CHATWOOT_WEBHOOK_SECRET", "").strip()
CHATWOOT_REQUEST_TIMEOUT_SECONDS: Final = _env_float("CHATWOOT_REQUEST_TIMEOUT_SECONDS", 10.0)
CHATWOOT_MAX_RETRIES: Final = _env_int("CHATWOOT_MAX_RETRIES", 3)
CHATWOOT_RETRY_BACKOFF_SECONDS: Final = _env_float("CHATWOOT_RETRY_BACKOFF_SECONDS", 1.0)
