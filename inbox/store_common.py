"""Shared helpers for the PostgreSQL-backed inbox store."""

from __future__ import annotations

import hashlib
import os
from typing import Any, Final

from core.database import DatabasePoolUnavailable
from core.database import connect as pooled_connect

MAX_STORED_BODY_CHARS: Final = 8000
MAX_STORED_NAME_CHARS: Final = 64
MAX_STORED_TYPE_CHARS: Final = 32
# Meta BSUIDs (June 2026+) can be longer than phones. Treat this as a
# "sender id" length (phone or BSUID) so hashes stay stable.
MAX_STORED_PHONE_CHARS: Final = 128
MAX_STORED_MESSAGE_ID_CHARS: Final = 128


class MessageStoreUnavailable(RuntimeError):
    """Raised when the inbox store cannot be used."""


def _database_key(database_url: str) -> str:
    """Return a stable non-secret cache key for a database URL."""
    return hashlib.sha256(database_url.encode("utf-8")).hexdigest()


def _auto_migrate_enabled() -> bool:
    """Return True when runtime schema migration is enabled."""
    value = os.getenv("INBOX_AUTO_MIGRATE", "true")
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _sha256(value: str) -> str:
    """Return a SHA-256 hex digest, preserving empty strings as empty."""
    if not value:
        return ""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _psycopg_modules() -> tuple[Any, Any, Any]:
    """Import psycopg helpers or fail with a store-specific error."""
    try:
        import psycopg
        from psycopg.rows import dict_row
        from psycopg.types.json import Jsonb
    except ImportError as exc:
        raise MessageStoreUnavailable("psycopg is required for the admin inbox") from exc

    return psycopg, dict_row, Jsonb


def _connect(database_url: str, *, dict_rows: bool = False) -> Any:
    """Return a pooled PostgreSQL connection context manager."""
    if not database_url:
        raise MessageStoreUnavailable("DATABASE_URL is not configured")

    try:
        return pooled_connect(database_url, dict_rows=dict_rows)
    except DatabasePoolUnavailable as exc:
        raise MessageStoreUnavailable(str(exc)) from exc
