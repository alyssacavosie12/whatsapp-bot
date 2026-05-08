"""PostgreSQL-backed admin inbox for WhatsApp messages."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, cast

from core.database import DatabasePoolUnavailable
from core.database import connect as pooled_connect
from core.text_utils import sanitize_untrusted_text

MAX_STORED_BODY_CHARS: Final = 8000
MAX_STORED_NAME_CHARS: Final = 64
MAX_STORED_TYPE_CHARS: Final = 32
# Meta BSUIDs (June 2026+) can be longer than phones. We treat this limit as
# "sender id" length (phone or BSUID) so hashes stay stable and deletions
# remain possible.
MAX_STORED_PHONE_CHARS: Final = 128
MAX_STORED_MESSAGE_ID_CHARS: Final = 128

_SCHEMA_READY: set[str] = set()


class MessageStoreUnavailable(RuntimeError):
    """Raised when the inbox store cannot be used."""


@dataclass(frozen=True)
class InboxMessage:
    """One sanitized admin inbox message row."""

    id: int
    whatsapp_message_id: str
    direction: str
    sender_phone: str
    sender_phone_masked: str
    sender_name: str
    message_type: str
    body: str
    body_encrypted: bool
    body_length: int
    created_at: datetime
    deleted_at: datetime | None
    deleted_by: str


def _database_key(database_url: str) -> str:
    return hashlib.sha256(database_url.encode("utf-8")).hexdigest()


def _auto_migrate_enabled() -> bool:
    value = os.getenv("INBOX_AUTO_MIGRATE", "true")
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _sha256(value: str) -> str:
    if not value:
        return ""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _psycopg_modules() -> tuple[Any, Any, Any]:
    try:
        import psycopg
        from psycopg.rows import dict_row
        from psycopg.types.json import Jsonb
    except ImportError as exc:
        raise MessageStoreUnavailable("psycopg is required for the admin inbox") from exc

    return psycopg, dict_row, Jsonb


def _connect(database_url: str, *, dict_rows: bool = False) -> Any:
    if not database_url:
        raise MessageStoreUnavailable("DATABASE_URL is not configured")

    try:
        return pooled_connect(database_url, dict_rows=dict_rows)
    except DatabasePoolUnavailable as exc:
        raise MessageStoreUnavailable(str(exc)) from exc


def _fernet(encryption_key: str) -> Any | None:
    if not encryption_key:
        return None

    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise MessageStoreUnavailable(
            "cryptography is required when INBOX_ENCRYPTION_KEY is set"
        ) from exc

    try:
        return Fernet(encryption_key.encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise MessageStoreUnavailable("INBOX_ENCRYPTION_KEY is invalid") from exc


def _prepare_body(body: object, encryption_key: str) -> tuple[str, bool, int, str]:
    safe_body = sanitize_untrusted_text(body, MAX_STORED_BODY_CHARS)
    body_length = len(safe_body)
    body_sha256 = _sha256(safe_body)

    cipher = _fernet(encryption_key)
    if not cipher:
        return safe_body, False, body_length, body_sha256

    encrypted = cipher.encrypt(safe_body.encode("utf-8")).decode("utf-8")
    return encrypted, True, body_length, body_sha256


def _prepare_sensitive_field(
    value: object,
    max_chars: int,
    encryption_key: str,
) -> tuple[str, bool, str]:
    safe_value = sanitize_untrusted_text(value, max_chars)
    value_hash = _sha256(safe_value)

    cipher = _fernet(encryption_key)
    if not cipher or not safe_value:
        return safe_value, False, value_hash

    encrypted = cipher.encrypt(safe_value.encode("utf-8")).decode("utf-8")
    return encrypted, True, value_hash


def _read_body(body: str, encrypted: bool, encryption_key: str) -> str:
    if not encrypted:
        return body

    cipher = _fernet(encryption_key)
    if not cipher:
        return "[encrypted message unavailable: INBOX_ENCRYPTION_KEY is not set]"

    try:
        return cast(str, cipher.decrypt(body.encode("utf-8")).decode("utf-8"))
    except Exception:
        return "[encrypted message unavailable: decrypt failed]"


def _read_sensitive_field(
    value: str,
    encrypted: bool,
    encryption_key: str,
    *,
    fallback: str = "",
) -> str:
    if not encrypted:
        return value

    cipher = _fernet(encryption_key)
    if not cipher:
        return fallback

    try:
        return cast(str, cipher.decrypt(value.encode("utf-8")).decode("utf-8"))
    except Exception:
        return fallback


def ensure_schema(database_url: str) -> None:
    """Create inbox tables at runtime.

    Railway private networking is runtime-only, so migrations must not depend on
    build-time database access.
    """
    key = _database_key(database_url)
    if key in _SCHEMA_READY:
        return

    if not _auto_migrate_enabled():
        _SCHEMA_READY.add(key)
        return

    with _connect(database_url) as conn:
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
                    ADD COLUMN IF NOT EXISTS sender_phone_encrypted BOOLEAN
                        NOT NULL DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS sender_phone_hash TEXT
                        NOT NULL DEFAULT '',
                    ADD COLUMN IF NOT EXISTS sender_name_encrypted BOOLEAN
                        NOT NULL DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS sender_name_hash TEXT
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
            # BSUID readiness: legacy rows had UNIQUE on phone hash. Drop it
            # (some Postgres versions name it inbox_opt_outs_sender_phone_hash_key,
            # IF EXISTS keeps this idempotent), add the new external-id columns,
            # backfill them from the phone columns, and put a partial unique
            # index on the new column so empty external_id_hash rows (legacy
            # phone-only) don't conflict.
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
            # Prefer NULLs over empty strings for optional fields so
            # redaction/ARCO deletion does not leave "empty value" artifacts.
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


def cleanup_expired_messages(database_url: str, retention_days: int) -> int:
    """Hard-delete messages and older audit events past the retention window."""
    if retention_days <= 0:
        return 0

    ensure_schema(database_url)

    with _connect(database_url) as conn:
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


def record_incoming_message(
    database_url: str,
    *,
    whatsapp_message_id: str,
    sender_phone: str,
    sender_phone_masked: str,
    sender_name: str,
    message_type: str,
    body: object,
    encryption_key: str = "",
    retention_days: int = 30,
) -> None:
    """Store one incoming webhook message."""
    ensure_schema(database_url)

    safe_message_id = sanitize_untrusted_text(
        whatsapp_message_id,
        MAX_STORED_MESSAGE_ID_CHARS,
    )
    safe_masked_phone = sanitize_untrusted_text(
        sender_phone_masked,
        MAX_STORED_PHONE_CHARS,
    )
    stored_phone, phone_encrypted, phone_hash = _prepare_sensitive_field(
        sender_phone,
        MAX_STORED_PHONE_CHARS,
        encryption_key,
    )
    stored_sender_name, sender_name_encrypted, sender_name_hash = _prepare_sensitive_field(
        sender_name,
        MAX_STORED_NAME_CHARS,
        encryption_key,
    )
    safe_message_type = sanitize_untrusted_text(message_type, MAX_STORED_TYPE_CHARS)
    stored_body, body_encrypted, body_length, body_sha256 = _prepare_body(
        body,
        encryption_key,
    )

    with _connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO inbox_messages (
                    whatsapp_message_id,
                    direction,
                    sender_phone,
                    sender_phone_masked,
                    sender_phone_encrypted,
                    sender_phone_hash,
                    sender_name,
                    sender_name_encrypted,
                    sender_name_hash,
                    message_type,
                    body,
                    body_encrypted,
                    body_length,
                    body_sha256
                )
                VALUES (
                    %s, 'incoming', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (whatsapp_message_id) DO NOTHING
                """,
                (
                    safe_message_id or None,
                    stored_phone,
                    safe_masked_phone,
                    phone_encrypted,
                    phone_hash,
                    stored_sender_name,
                    sender_name_encrypted,
                    sender_name_hash,
                    safe_message_type,
                    stored_body,
                    body_encrypted,
                    body_length,
                    body_sha256,
                ),
            )


def record_opt_in_proof(
    database_url: str,
    *,
    whatsapp_message_id: str,
    sender_phone: str,
    proof_type: str = "inbound_customer_initiated",
    proof_source: str = "whatsapp_webhook",
    evidence: dict[str, Any] | str | None = None,
    proof_secret: str = "",
    encryption_key: str = "",
) -> None:
    """Store a tamper-evident proof that the user initiated the conversation."""
    if not proof_secret:
        raise MessageStoreUnavailable("INBOX_PROOF_SECRET is not configured")

    ensure_schema(database_url)

    safe_message_id = sanitize_untrusted_text(
        whatsapp_message_id,
        MAX_STORED_MESSAGE_ID_CHARS,
    )
    stored_phone, phone_encrypted, phone_hash = _prepare_sensitive_field(
        sender_phone,
        MAX_STORED_PHONE_CHARS,
        encryption_key,
    )
    safe_proof_type = sanitize_untrusted_text(proof_type, MAX_STORED_TYPE_CHARS)
    safe_proof_source = sanitize_untrusted_text(proof_source, MAX_STORED_TYPE_CHARS)
    evidence_text = (
        json.dumps(evidence or {}, sort_keys=True, separators=(",", ":"))
        if not isinstance(evidence, str)
        else evidence
    )
    stored_evidence, evidence_encrypted, evidence_sha256 = _prepare_sensitive_field(
        evidence_text,
        MAX_STORED_BODY_CHARS,
        encryption_key,
    )
    proof_payload = json.dumps(
        {
            "evidence_sha256": evidence_sha256,
            "message_id": safe_message_id,
            "phone_hash": phone_hash,
            "proof_source": safe_proof_source,
            "proof_type": safe_proof_type,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    proof_hmac = hmac.new(
        proof_secret.encode("utf-8"),
        proof_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    with _connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO inbox_opt_in_proofs (
                    whatsapp_message_id,
                    sender_phone,
                    sender_phone_encrypted,
                    sender_phone_hash,
                    proof_type,
                    proof_source,
                    evidence,
                    evidence_encrypted,
                    evidence_sha256,
                    proof_hmac
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (whatsapp_message_id) DO NOTHING
                """,
                (
                    safe_message_id or None,
                    stored_phone,
                    phone_encrypted,
                    phone_hash,
                    safe_proof_type,
                    safe_proof_source,
                    stored_evidence,
                    evidence_encrypted,
                    evidence_sha256,
                    proof_hmac,
                ),
            )


def has_incoming_message_for_sender(database_url: str, sender_external_id: str) -> bool:
    """Return True when a sender already has an inbound inbox message."""
    ensure_schema(database_url)

    safe_sender = sanitize_untrusted_text(sender_external_id, MAX_STORED_PHONE_CHARS)
    sender_hash = _sha256(safe_sender)
    if not sender_hash:
        return False

    with _connect(database_url, dict_rows=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM inbox_messages
                WHERE direction = 'incoming'
                    AND sender_phone_hash = %s
                LIMIT 1
                """,
                (sender_hash,),
            )
            return bool(cur.fetchall())


def list_messages(
    database_url: str,
    *,
    query: str = "",
    limit: int = 100,
    include_deleted: bool = False,
    encryption_key: str = "",
) -> list[InboxMessage]:
    """Return recent inbox messages."""
    ensure_schema(database_url)

    safe_limit = max(1, min(int(limit or 100), 500))
    safe_query = str(query or "").strip()
    params: list[Any] = []

    if safe_query:
        like = f"%{safe_query}%"
        query_hash = _sha256(safe_query)
        params.extend([query_hash, query_hash, like, like, like, like])

        if include_deleted:
            sql = """
                SELECT
                    id,
                    whatsapp_message_id,
                    direction,
                    sender_phone,
                    sender_phone_masked,
                    sender_phone_encrypted,
                    sender_name,
                    sender_name_encrypted,
                    message_type,
                    body,
                    body_encrypted,
                    body_length,
                    created_at,
                    deleted_at,
                    deleted_by
                FROM inbox_messages
                WHERE (
                    sender_phone_hash = %s
                    OR sender_name_hash = %s
                    OR sender_phone_masked ILIKE %s
                    OR (sender_phone_encrypted = FALSE AND sender_phone ILIKE %s)
                    OR (sender_name_encrypted = FALSE AND sender_name ILIKE %s)
                    OR (body_encrypted = FALSE AND body ILIKE %s)
                )
                ORDER BY created_at DESC
                LIMIT %s
            """
        else:
            sql = """
                SELECT
                    id,
                    whatsapp_message_id,
                    direction,
                    sender_phone,
                    sender_phone_masked,
                    sender_phone_encrypted,
                    sender_name,
                    sender_name_encrypted,
                    message_type,
                    body,
                    body_encrypted,
                    body_length,
                    created_at,
                    deleted_at,
                    deleted_by
                FROM inbox_messages
                WHERE deleted_at IS NULL
                    AND (
                        sender_phone_hash = %s
                        OR sender_name_hash = %s
                        OR sender_phone_masked ILIKE %s
                        OR (sender_phone_encrypted = FALSE AND sender_phone ILIKE %s)
                        OR (sender_name_encrypted = FALSE AND sender_name ILIKE %s)
                        OR (body_encrypted = FALSE AND body ILIKE %s)
                    )
                ORDER BY created_at DESC
                LIMIT %s
            """
    elif include_deleted:
        sql = """
            SELECT
                id,
                whatsapp_message_id,
                direction,
                sender_phone,
                sender_phone_masked,
                sender_phone_encrypted,
                sender_name,
                sender_name_encrypted,
                message_type,
                body,
                body_encrypted,
                body_length,
                created_at,
                deleted_at,
                deleted_by
            FROM inbox_messages
            ORDER BY created_at DESC
            LIMIT %s
        """
    else:
        sql = """
        SELECT
            id,
            whatsapp_message_id,
            direction,
            sender_phone,
            sender_phone_masked,
            sender_phone_encrypted,
            sender_name,
            sender_name_encrypted,
            message_type,
            body,
            body_encrypted,
            body_length,
            created_at,
            deleted_at,
            deleted_by
        FROM inbox_messages
        WHERE deleted_at IS NULL
        ORDER BY created_at DESC
        LIMIT %s
        """

    params.append(safe_limit)

    with _connect(database_url, dict_rows=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return [
        InboxMessage(
            id=row["id"],
            whatsapp_message_id=row["whatsapp_message_id"] or "",
            direction=row["direction"],
            sender_phone=_read_sensitive_field(
                row["sender_phone"],
                row["sender_phone_encrypted"],
                encryption_key,
                fallback=row["sender_phone_masked"],
            ),
            sender_phone_masked=row["sender_phone_masked"],
            sender_name=_read_sensitive_field(
                row["sender_name"],
                row["sender_name_encrypted"],
                encryption_key,
                fallback="",
            ),
            message_type=row["message_type"],
            body=_read_body(row["body"], row["body_encrypted"], encryption_key),
            body_encrypted=row["body_encrypted"],
            body_length=row["body_length"],
            created_at=row["created_at"],
            deleted_at=row["deleted_at"],
            deleted_by=row["deleted_by"],
        )
        for row in rows
    ]


def soft_delete_message(
    database_url: str,
    *,
    message_id: int,
    deleted_by: str,
) -> bool:
    """Soft-delete a message from the inbox."""
    ensure_schema(database_url)

    with _connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE inbox_messages
                SET deleted_at = now(), deleted_by = %s
                WHERE id = %s AND deleted_at IS NULL
                """,
                (
                    sanitize_untrusted_text(deleted_by, MAX_STORED_NAME_CHARS),
                    message_id,
                ),
            )
            rowcount = int(cur.rowcount or 0)
            return rowcount > 0


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
) -> None:
    """Append an admin inbox audit event."""
    ensure_schema(database_url)
    _psycopg, _dict_row, jsonb = _psycopg_modules()

    with _connect(database_url) as conn:
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


# ─── Opt-out (LFPDPPP Oposición / CCPA) ────────────────────────────


MAX_STORED_OPT_OUT_KEYWORD_CHARS: Final = 64
MAX_STORED_OPT_OUT_SOURCE_CHARS: Final = 32
MAX_STORED_LANGUAGE_CHARS: Final = 8


def record_opt_out(
    database_url: str,
    *,
    sender_external_id: str,
    sender_external_id_type: str = "phone",
    source: str,
    keyword_used: str = "",
    language: str = "",
    encryption_key: str = "",
    proof_secret: str = "",
) -> bool:
    """Record an opt-out request. Returns True if newly inserted, False if duplicate.

    Idempotent on `sender_external_id_hash` — a second STOP from the same
    user (phone or BSUID) does not duplicate the record.

    To minimize stored personal data, this function does *not* persist the
    plaintext external id by default. The opt-out check uses
    `sender_external_id_hash` and the HMAC proof (`evidence_hmac`) instead.
    """
    if not proof_secret:
        raise MessageStoreUnavailable("INBOX_PROOF_SECRET is not configured")
    if not sender_external_id:
        raise MessageStoreUnavailable("Cannot record opt-out without an external id")

    ensure_schema(database_url)

    safe_external_id = sanitize_untrusted_text(sender_external_id, MAX_STORED_PHONE_CHARS)
    external_id_hash = _sha256(safe_external_id)
    if not external_id_hash:
        raise MessageStoreUnavailable("Cannot record opt-out for an empty external id")

    safe_external_id_type = sanitize_untrusted_text(
        sender_external_id_type, MAX_STORED_LANGUAGE_CHARS
    )
    if safe_external_id_type not in {"phone", "bsuid"}:
        safe_external_id_type = "phone"

    # Keep optional PII columns NULL by default (hash + HMAC proof is enough).
    stored_phone: str | None = None
    phone_encrypted = False
    phone_hash: str | None = None
    stored_external_id: str | None = None

    safe_source = sanitize_untrusted_text(source, MAX_STORED_OPT_OUT_SOURCE_CHARS)
    safe_keyword = sanitize_untrusted_text(keyword_used, MAX_STORED_OPT_OUT_KEYWORD_CHARS) or None
    safe_language = sanitize_untrusted_text(language, MAX_STORED_LANGUAGE_CHARS) or None

    proof_payload = json.dumps(
        {
            "external_id_hash": external_id_hash,
            "external_id_type": safe_external_id_type,
            "source": safe_source,
            "keyword_used": safe_keyword,
            "language": safe_language,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    evidence_hmac = hmac.new(
        proof_secret.encode("utf-8"),
        proof_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    with _connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO inbox_opt_outs (
                    sender_phone_hash,
                    sender_phone,
                    sender_phone_encrypted,
                    sender_external_id,
                    sender_external_id_type,
                    sender_external_id_hash,
                    source,
                    keyword_used,
                    language,
                    evidence_hmac
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sender_external_id_hash) DO NOTHING
                """,
                (
                    phone_hash,
                    stored_phone,
                    phone_encrypted,
                    stored_external_id,
                    safe_external_id_type,
                    external_id_hash,
                    safe_source,
                    safe_keyword,
                    safe_language,
                    evidence_hmac,
                ),
            )
            return int(cur.rowcount or 0) > 0


def is_opted_out(database_url: str, sender_external_id: str) -> bool:
    """Return True when the sender (phone OR BSUID) has a recorded opt-out.

    Lookup is by external-id hash so phone and BSUID senders share one
    code path. The schema is ensured on first call per process; subsequent
    calls are a single indexed SELECT.
    """
    if not sender_external_id:
        return False

    external_id_hash = _sha256(sanitize_untrusted_text(sender_external_id, MAX_STORED_PHONE_CHARS))
    if not external_id_hash:
        return False

    ensure_schema(database_url)

    with _connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM inbox_opt_outs
                WHERE sender_external_id_hash = %s LIMIT 1
                """,
                (external_id_hash,),
            )
            return cur.fetchone() is not None


def delete_user_data(
    database_url: str,
    *,
    sender_external_id: str,
    delete_opt_out_record: bool = False,
) -> dict[str, int]:
    """Hard-delete all stored records for one user (ARCO Cancelación).

    Accepts either an E.164 phone or a BSUID. Message storage and opt-out
    lookups key on SHA-256 hashes of the sender id, so both phone and BSUID
    subjects delete via the same hash.

    The opt-out row is retained by default — it's the legal evidence
    needed to prove ongoing non-consent. Pass
    `delete_opt_out_record=True` only when the user accepts that future
    inbound messages will be processed as new contacts.
    """
    if not sender_external_id:
        raise MessageStoreUnavailable("Cannot delete data for an empty id")

    safe_external_id = sanitize_untrusted_text(sender_external_id, MAX_STORED_PHONE_CHARS)
    external_id_hash = _sha256(safe_external_id)
    if not external_id_hash:
        raise MessageStoreUnavailable("Cannot delete data for an empty id")

    ensure_schema(database_url)

    counts: dict[str, int] = {}
    with _connect(database_url) as conn:
        with conn.cursor() as cur:
            # Legacy tables key on phone hash; equal to external-id hash
            # for phone senders (see backfill in ensure_schema).
            cur.execute(
                "DELETE FROM inbox_messages WHERE sender_phone_hash = %s",
                (external_id_hash,),
            )
            counts["messages"] = int(cur.rowcount or 0)

            cur.execute(
                "DELETE FROM inbox_opt_in_proofs WHERE sender_phone_hash = %s",
                (external_id_hash,),
            )
            counts["opt_in_proofs"] = int(cur.rowcount or 0)

            if delete_opt_out_record:
                cur.execute(
                    """
                    DELETE FROM inbox_opt_outs
                    WHERE sender_external_id_hash = %s
                    """,
                    (external_id_hash,),
                )
                counts["opt_outs"] = int(cur.rowcount or 0)
            else:
                # Keep the opt-out evidence row (hash + HMAC) but scrub any
                # plaintext/encrypted identifiers so Cancelación does not leave
                # residual PII.
                cur.execute(
                    """
                    UPDATE inbox_opt_outs
                    SET
                        sender_phone_hash = NULL,
                        sender_phone = NULL,
                        sender_phone_encrypted = FALSE,
                        sender_external_id = NULL
                    WHERE sender_external_id_hash = %s
                    """,
                    (external_id_hash,),
                )
                counts["opt_outs"] = 0

    return counts
