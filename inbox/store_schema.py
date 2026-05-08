"""Runtime schema management and retention cleanup for the inbox store."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from inbox.store_common import _auto_migrate_enabled, _connect, _database_key

ConnectFactory = Callable[..., Any]

_SCHEMA_READY: set[str] = set()


def ensure_schema(
    database_url: str,
    *,
    connect_factory: ConnectFactory = _connect,
    auto_migrate_enabled: Callable[[], bool] = _auto_migrate_enabled,
) -> None:
    """Create inbox tables at runtime.

    Railway private networking is runtime-only, so migrations must not depend
    on build-time database access.
    """
    key = _database_key(database_url)
    if key in _SCHEMA_READY:
        return

    if not auto_migrate_enabled():
        _SCHEMA_READY.add(key)
        return

    with connect_factory(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS inbox_messages (
                    id BIGSERIAL PRIMARY KEY,
                    whatsapp_message_id TEXT UNIQUE,
                    direction TEXT NOT NULL
                        CHECK (direction IN ('incoming', 'outgoing')),
                    sender_phone TEXT NOT NULL DEFAULT '',
                    sender_phone_masked TEXT NOT NULL DEFAULT '',
                    sender_phone_encrypted BOOLEAN NOT NULL DEFAULT FALSE,
                    sender_phone_hash TEXT NOT NULL DEFAULT '',
                    sender_name TEXT NOT NULL DEFAULT '',
                    sender_name_encrypted BOOLEAN NOT NULL DEFAULT FALSE,
                    sender_name_hash TEXT NOT NULL DEFAULT '',
                    message_type TEXT NOT NULL DEFAULT '',
                    body TEXT NOT NULL DEFAULT '',
                    body_encrypted BOOLEAN NOT NULL DEFAULT FALSE,
                    body_length INTEGER NOT NULL DEFAULT 0,
                    body_sha256 TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    deleted_at TIMESTAMPTZ,
                    deleted_by TEXT NOT NULL DEFAULT ''
                )
                """
            )
            cur.execute(
                """
                ALTER TABLE inbox_messages
                    ADD COLUMN IF NOT EXISTS sender_phone_masked TEXT
                        NOT NULL DEFAULT '',
                    ADD COLUMN IF NOT EXISTS sender_phone_encrypted BOOLEAN
                        NOT NULL DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS sender_phone_hash TEXT
                        NOT NULL DEFAULT '',
                    ADD COLUMN IF NOT EXISTS sender_name TEXT
                        NOT NULL DEFAULT '',
                    ADD COLUMN IF NOT EXISTS sender_name_encrypted BOOLEAN
                        NOT NULL DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS sender_name_hash TEXT
                        NOT NULL DEFAULT '',
                    ADD COLUMN IF NOT EXISTS message_type TEXT
                        NOT NULL DEFAULT '',
                    ADD COLUMN IF NOT EXISTS body TEXT
                        NOT NULL DEFAULT '',
                    ADD COLUMN IF NOT EXISTS body_encrypted BOOLEAN
                        NOT NULL DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS body_length INTEGER
                        NOT NULL DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS body_sha256 TEXT
                        NOT NULL DEFAULT '',
                    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ,
                    ADD COLUMN IF NOT EXISTS deleted_by TEXT
                        NOT NULL DEFAULT ''
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS inbox_messages_created_idx
                    ON inbox_messages (created_at DESC)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS inbox_messages_sender_phone_idx
                    ON inbox_messages (sender_phone)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS inbox_messages_sender_phone_hash_idx
                    ON inbox_messages (sender_phone_hash)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS inbox_messages_sender_name_hash_idx
                    ON inbox_messages (sender_name_hash)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS inbox_audit_events (
                    id BIGSERIAL PRIMARY KEY,
                    actor TEXT NOT NULL,
                    actor_role TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_message_id BIGINT,
                    ip_address TEXT NOT NULL DEFAULT '',
                    user_agent TEXT NOT NULL DEFAULT '',
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS inbox_audit_created_idx
                    ON inbox_audit_events (created_at DESC)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS inbox_opt_in_proofs (
                    id BIGSERIAL PRIMARY KEY,
                    whatsapp_message_id TEXT UNIQUE,
                    sender_phone TEXT NOT NULL DEFAULT '',
                    sender_phone_encrypted BOOLEAN NOT NULL DEFAULT FALSE,
                    sender_phone_hash TEXT NOT NULL DEFAULT '',
                    proof_type TEXT NOT NULL DEFAULT '',
                    proof_source TEXT NOT NULL DEFAULT '',
                    evidence TEXT NOT NULL DEFAULT '',
                    evidence_encrypted BOOLEAN NOT NULL DEFAULT FALSE,
                    evidence_sha256 TEXT NOT NULL DEFAULT '',
                    proof_hmac TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS inbox_opt_in_proofs_created_idx
                    ON inbox_opt_in_proofs (created_at DESC)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS inbox_opt_in_proofs_sender_phone_hash_idx
                    ON inbox_opt_in_proofs (sender_phone_hash)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS inbox_opt_outs (
                    id BIGSERIAL PRIMARY KEY,
                    sender_phone_hash TEXT,
                    sender_phone TEXT,
                    sender_phone_encrypted BOOLEAN NOT NULL DEFAULT FALSE,
                    sender_external_id TEXT,
                    sender_external_id_type TEXT NOT NULL DEFAULT 'phone',
                    sender_external_id_hash TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    keyword_used TEXT,
                    language TEXT,
                    evidence_hmac TEXT NOT NULL DEFAULT '',
                    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute(
                """
                ALTER TABLE inbox_opt_outs
                    ADD COLUMN IF NOT EXISTS sender_external_id TEXT,
                    ADD COLUMN IF NOT EXISTS sender_external_id_type TEXT
                        NOT NULL DEFAULT 'phone',
                    ADD COLUMN IF NOT EXISTS sender_external_id_hash TEXT
                        NOT NULL DEFAULT ''
                """
            )
            cur.execute(
                """
                ALTER TABLE inbox_opt_outs
                    DROP CONSTRAINT IF EXISTS inbox_opt_outs_sender_phone_hash_key
                """
            )
            cur.execute(
                """
                UPDATE inbox_opt_outs
                SET
                    sender_external_id = sender_phone,
                    sender_external_id_type = 'phone',
                    sender_external_id_hash = sender_phone_hash
                WHERE (sender_external_id_hash IS NULL OR sender_external_id_hash = '')
                    AND sender_phone_hash IS NOT NULL
                    AND sender_phone_hash != ''
                """
            )
            cur.execute(
                """
                ALTER TABLE inbox_opt_outs
                    ALTER COLUMN sender_phone_hash DROP NOT NULL,
                    ALTER COLUMN sender_phone_hash DROP DEFAULT,
                    ALTER COLUMN sender_phone DROP NOT NULL,
                    ALTER COLUMN sender_phone DROP DEFAULT,
                    ALTER COLUMN sender_external_id DROP NOT NULL,
                    ALTER COLUMN sender_external_id DROP DEFAULT,
                    ALTER COLUMN keyword_used DROP NOT NULL,
                    ALTER COLUMN keyword_used DROP DEFAULT,
                    ALTER COLUMN language DROP NOT NULL,
                    ALTER COLUMN language DROP DEFAULT
                """
            )
            cur.execute(
                """
                UPDATE inbox_opt_outs
                SET
                    sender_phone_hash = NULLIF(sender_phone_hash, ''),
                    sender_phone = NULLIF(sender_phone, ''),
                    sender_external_id = NULLIF(sender_external_id, ''),
                    keyword_used = NULLIF(keyword_used, ''),
                    language = NULLIF(language, '')
                """
            )
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS inbox_opt_outs_external_id_hash_uniq
                    ON inbox_opt_outs (sender_external_id_hash)
                    WHERE sender_external_id_hash != ''
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS inbox_opt_outs_recorded_idx
                    ON inbox_opt_outs (recorded_at DESC)
                """
            )

    _SCHEMA_READY.add(key)


def cleanup_expired_messages(
    database_url: str,
    retention_days: int,
    *,
    connect_factory: ConnectFactory = _connect,
    ensure_schema_func: Callable[[str], None] | None = None,
) -> int:
    """Hard-delete messages and older audit events past the retention window."""
    if retention_days <= 0:
        return 0

    if ensure_schema_func is None:

        def ensure_schema_with_factory(url: str) -> None:
            ensure_schema(url, connect_factory=connect_factory)

        ensure_schema_func = ensure_schema_with_factory

    ensure_schema_func(database_url)

    with connect_factory(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM inbox_messages
                WHERE created_at < now() - (%s * INTERVAL '1 day')
                """,
                (retention_days,),
            )
            deleted_messages = int(cur.rowcount or 0)
            cur.execute(
                """
                DELETE FROM inbox_audit_events
                WHERE created_at < now() - (%s * INTERVAL '1 day')
                """,
                (retention_days + 30,),
            )
            cur.execute(
                """
                DELETE FROM inbox_opt_in_proofs
                WHERE created_at < now() - (%s * INTERVAL '1 day')
                """,
                (retention_days + 30,),
            )

    return deleted_messages
