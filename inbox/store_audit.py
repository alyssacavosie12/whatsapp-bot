"""Audit-event persistence for the admin inbox."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.text_utils import sanitize_untrusted_text
from inbox.store_common import (
    MAX_STORED_NAME_CHARS,
    MAX_STORED_TYPE_CHARS,
    _connect,
    _psycopg_modules,
)
from inbox.store_schema import ensure_schema

ConnectFactory = Callable[..., Any]
PsycopgModulesFactory = Callable[[], tuple[Any, Any, Any]]


def record_audit_event(
    database_url: str,
    *,
    actor: str,
    actor_role: str,
    action: str,
    target_message_id: int | None = None,
    ip_address: str = "",
    user_agent: str = "",
    metadata: dict[str, Any] | None = None,
    connect_factory: ConnectFactory = _connect,
    psycopg_modules: PsycopgModulesFactory = _psycopg_modules,
    ensure_schema_func: Callable[[str], None] = ensure_schema,
) -> None:
    """Append an admin inbox audit event."""
    ensure_schema_func(database_url)
    _psycopg, _dict_row, jsonb = psycopg_modules()

    with connect_factory(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO inbox_audit_events (
                    actor,
                    actor_role,
                    action,
                    target_message_id,
                    ip_address,
                    user_agent,
                    metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    sanitize_untrusted_text(actor, MAX_STORED_NAME_CHARS),
                    sanitize_untrusted_text(actor_role, MAX_STORED_TYPE_CHARS),
                    sanitize_untrusted_text(action, MAX_STORED_TYPE_CHARS),
                    target_message_id,
                    sanitize_untrusted_text(ip_address, 64),
                    sanitize_untrusted_text(user_agent, 256),
                    jsonb(metadata or {}),
                ),
            )
