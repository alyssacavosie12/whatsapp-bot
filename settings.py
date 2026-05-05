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
MAX_CONTENT_LENGTH = _env_int("MAX_CONTENT_LENGTH", 65536)
MAX_INCOMING_TEXT_CHARS = _env_int("MAX_INCOMING_TEXT_CHARS", 4000)


# ─── Dedup ───────────────────────────────────────────────────

REDIS_URL = os.getenv("REDIS_URL", "").strip()
MESSAGE_TTL_SECONDS = _env_int("MESSAGE_TTL_SECONDS", 60 * 60)
MAX_LOCAL_DEDUP_SIZE = _env_int("MAX_LOCAL_DEDUP_SIZE", 10_000)


# ─── Rate limiting ───────────────────────────────────────────

PHONE_RATE_LIMIT_MAX_MESSAGES = _env_int("PHONE_RATE_LIMIT_MAX_MESSAGES", 20)
PHONE_RATE_LIMIT_WINDOW_SECONDS = _env_int("PHONE_RATE_LIMIT_WINDOW_SECONDS", 60)


# ─── Anthropic ───────────────────────────────────────────────

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip()
ANTHROPIC_MAX_TOKENS = _env_int("ANTHROPIC_MAX_TOKENS", 300)
ANTHROPIC_TIMEOUT_SECONDS = _env_int("ANTHROPIC_TIMEOUT_SECONDS", 30)


# ─── Bot behavior ────────────────────────────────────────────

BOT_DISCLOSURE = _env_bool("BOT_DISCLOSURE", default=False)
TEAM_NOTIFY_PHONE = os.getenv("TEAM_NOTIFY_PHONE", "").strip()
