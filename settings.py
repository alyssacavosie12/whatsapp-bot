"""Environment configuration for the WhatsApp bot."""

from __future__ import annotations

import os

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


# ─── WhatsApp / Meta ─────────────────────────────────────────

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "").strip()
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "tulum-btx-bot-token").strip()
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v21.0").strip()

META_APP_SECRET = os.getenv("META_APP_SECRET", "").strip()
# Retained for older Railway configs; app.py now refuses unsigned POST webhooks.
ALLOW_UNSIGNED_WEBHOOKS = _env_bool("ALLOW_UNSIGNED_WEBHOOKS", default=False)
MAX_CONTENT_LENGTH = _env_int("MAX_CONTENT_LENGTH", 65536)
MAX_INCOMING_TEXT_CHARS = _env_int("MAX_INCOMING_TEXT_CHARS", 4000)
LOG_INCOMING_MESSAGES = _env_bool("LOG_INCOMING_MESSAGES", default=False)
INCOMING_MESSAGE_LOG_MAX_CHARS = _env_int("INCOMING_MESSAGE_LOG_MAX_CHARS", 1000)


# ─── Flask / HTTP hardening ──────────────────────────────────

FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "").strip()
FORCE_HTTPS = _env_bool("FORCE_HTTPS", default=False)


# ─── Dedup ───────────────────────────────────────────────────

REDIS_URL = os.getenv("REDIS_URL", "").strip()
MESSAGE_TTL_SECONDS = _env_int("MESSAGE_TTL_SECONDS", 60 * 60)
MAX_LOCAL_DEDUP_SIZE = _env_int("MAX_LOCAL_DEDUP_SIZE", 10_000)


# ─── Rate limiting ───────────────────────────────────────────

PHONE_RATE_LIMIT_MAX_MESSAGES = _env_int("PHONE_RATE_LIMIT_MAX_MESSAGES", 20)
PHONE_RATE_LIMIT_WINDOW_SECONDS = _env_int("PHONE_RATE_LIMIT_WINDOW_SECONDS", 60)
WEBHOOK_RATE_LIMIT = os.getenv("WEBHOOK_RATE_LIMIT", "300 per minute").strip()
RATE_LIMIT_STORAGE_URL = os.getenv("RATE_LIMIT_STORAGE_URL", REDIS_URL).strip()


# ─── Anthropic ───────────────────────────────────────────────

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip()
ANTHROPIC_MAX_TOKENS = _env_int("ANTHROPIC_MAX_TOKENS", 300)
ANTHROPIC_TIMEOUT_SECONDS = _env_int("ANTHROPIC_TIMEOUT_SECONDS", 30)


# ─── Bot behavior ────────────────────────────────────────────

BOT_DISCLOSURE = _env_bool("BOT_DISCLOSURE", default=True)
TEAM_NOTIFY_PHONE = os.getenv("TEAM_NOTIFY_PHONE", "").strip()


# ─── Admin inbox ──────────────────────────────────────────────

INBOX_ENABLED = _env_bool("INBOX_ENABLED", default=True)
INBOX_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
INBOX_RETENTION_DAYS = _env_int("INBOX_RETENTION_DAYS", 30)
INBOX_REQUIRE_ENCRYPTION = _env_bool("INBOX_REQUIRE_ENCRYPTION", default=True)
INBOX_ENCRYPTION_KEY = os.getenv("INBOX_ENCRYPTION_KEY", "").strip()
INBOX_CSRF_SECRET = os.getenv("INBOX_CSRF_SECRET", "").strip()
INBOX_PROOF_SECRET = os.getenv("INBOX_PROOF_SECRET", "").strip()
INBOX_AUTO_MIGRATE = _env_bool("INBOX_AUTO_MIGRATE", default=True)
INBOX_AUTH_MAX_FAILED_ATTEMPTS = _env_int("INBOX_AUTH_MAX_FAILED_ATTEMPTS", 5)
INBOX_AUTH_WINDOW_SECONDS = _env_int("INBOX_AUTH_WINDOW_SECONDS", 15 * 60)

INBOX_ADMIN_USERNAME = os.getenv("INBOX_ADMIN_USERNAME", "").strip()
INBOX_ADMIN_PASSWORD_HASH = os.getenv("INBOX_ADMIN_PASSWORD_HASH", "").strip()
INBOX_VIEWER_USERNAME = os.getenv("INBOX_VIEWER_USERNAME", "").strip()
INBOX_VIEWER_PASSWORD_HASH = os.getenv("INBOX_VIEWER_PASSWORD_HASH", "").strip()
