"""PostgreSQL-backed admin inbox for WhatsApp messages."""

from __future__ import annotations

from typing import Any, Final

from core.text_utils import sanitize_untrusted_text
from inbox import store_audit, store_opt_in, store_opt_outs, store_schema
from inbox.store_common import (
    MAX_STORED_MESSAGE_ID_CHARS,
    MAX_STORED_NAME_CHARS,
    MAX_STORED_PHONE_CHARS,
    MAX_STORED_TYPE_CHARS,
    MessageStoreUnavailable,
    _auto_migrate_enabled,
    _connect,
    _psycopg_modules,
    _sha256,
)
from inbox.store_common import (
    _database_key as _database_key,
)
from inbox.store_crypto import (
    _body_for_display,
    _prepare_body,
    _prepare_sensitive_field,
    _read_sensitive_field,
    _sensitive_field_for_display,
)
from inbox.store_crypto import (
    _fernet as _fernet,
)
from inbox.store_crypto import (
    _read_body as _read_body,
)
from inbox.store_models import (
    InboxConversationSummary,
    InboxDashboardStats,
    InboxMessage,
    InboxOptOutRecord,
)

__all__ = [
    "InboxConversationSummary",
    "InboxDashboardStats",
    "InboxMessage",
    "InboxOptOutRecord",
    "MessageStoreUnavailable",
    "_SCHEMA_READY",
    "_auto_migrate_enabled",
    "_connect",
    "_database_key",
    "_fernet",
    "_prepare_body",
    "_prepare_sensitive_field",
    "_psycopg_modules",
    "_read_body",
    "_read_sensitive_field",
    "_sha256",
    "cleanup_expired_messages",
    "delete_user_data",
    "ensure_schema",
    "get_conversation_messages",
    "get_dashboard_stats",
    "get_message_by_id",
    "has_incoming_message_for_sender",
    "is_opted_out",
    "list_conversations",
    "list_messages",
    "list_opt_out_records",
    "record_audit_event",
    "record_incoming_message",
    "record_opt_in_proof",
    "record_opt_out",
    "soft_delete_message",
]

_SCHEMA_READY = store_schema._SCHEMA_READY


def ensure_schema(database_url: str) -> None:
    """Create inbox tables at runtime."""
    store_schema.ensure_schema(
        database_url,
        connect_factory=_connect,
        auto_migrate_enabled=_auto_migrate_enabled,
    )


def cleanup_expired_messages(database_url: str, retention_days: int) -> int:
    """Hard-delete messages and older audit events past the retention window."""
    return store_schema.cleanup_expired_messages(
        database_url,
        retention_days,
        connect_factory=_connect,
        ensure_schema_func=ensure_schema,
    )


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
    store_opt_in.record_opt_in_proof(
        database_url,
        whatsapp_message_id=whatsapp_message_id,
        sender_phone=sender_phone,
        proof_type=proof_type,
        proof_source=proof_source,
        evidence=evidence,
        proof_secret=proof_secret,
        encryption_key=encryption_key,
        connect_factory=_connect,
        ensure_schema_func=ensure_schema,
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
    decrypt: bool = True,
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

    return [_row_to_inbox_message(row, encryption_key, decrypt=decrypt) for row in rows]


def _row_to_inbox_message(
    row: Any,
    encryption_key: str,
    *,
    decrypt: bool = True,
) -> InboxMessage:
    """Convert a DB row into an InboxMessage."""
    return InboxMessage(
        id=row["id"],
        whatsapp_message_id=row["whatsapp_message_id"] or "",
        direction=row["direction"],
        sender_phone=_sensitive_field_for_display(
            row["sender_phone"],
            row["sender_phone_encrypted"],
            encryption_key,
            decrypt=decrypt,
            fallback=row["sender_phone_masked"],
        ),
        sender_phone_masked=row["sender_phone_masked"],
        sender_name=_sensitive_field_for_display(
            row["sender_name"],
            row["sender_name_encrypted"],
            encryption_key,
            decrypt=decrypt,
            fallback="Encrypted contact" if row["sender_name_encrypted"] else "",
        ),
        message_type=row["message_type"],
        body=_body_for_display(
            row["body"],
            row["body_encrypted"],
            encryption_key,
            decrypt=decrypt,
        ),
        body_encrypted=row["body_encrypted"],
        body_length=row["body_length"],
        created_at=row["created_at"],
        deleted_at=row["deleted_at"],
        deleted_by=row["deleted_by"],
    )


def list_conversations(
    database_url: str,
    *,
    limit: int = 100,
    encryption_key: str = "",
    decrypt: bool = True,
) -> list[InboxConversationSummary]:
    """Return recent conversations grouped by sender hash."""
    ensure_schema(database_url)

    safe_limit = max(1, min(int(limit or 100), 500))

    with _connect(database_url, dict_rows=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH ranked AS (
                    SELECT
                        id,
                        sender_phone_hash,
                        sender_phone_masked,
                        sender_name,
                        sender_name_encrypted,
                        message_type,
                        body,
                        body_encrypted,
                        created_at,
                        COUNT(*) OVER (
                            PARTITION BY sender_phone_hash
                        ) AS message_count,
                        ROW_NUMBER() OVER (
                            PARTITION BY sender_phone_hash
                            ORDER BY created_at DESC, id DESC
                        ) AS row_number
                    FROM inbox_messages
                    WHERE deleted_at IS NULL
                        AND sender_phone_hash != ''
                )
                SELECT
                    sender_phone_hash,
                    sender_phone_masked,
                    sender_name,
                    sender_name_encrypted,
                    message_type,
                    body,
                    body_encrypted,
                    created_at,
                    message_count
                FROM ranked
                WHERE row_number = 1
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (safe_limit,),
            )
            rows = cur.fetchall()

    return [
        InboxConversationSummary(
            conversation_id=row["sender_phone_hash"],
            sender_phone_masked=row["sender_phone_masked"],
            sender_name=_read_sensitive_field(
                row["sender_name"],
                row["sender_name_encrypted"],
                encryption_key,
                fallback="",
            ),
            last_message_type=row["message_type"],
            last_body=_body_for_display(
                row["body"],
                row["body_encrypted"],
                encryption_key,
                decrypt=decrypt,
            ),
            last_body_encrypted=row["body_encrypted"],
            message_count=int(row["message_count"] or 0),
            last_message_at=row["created_at"],
        )
        for row in rows
    ]


def get_conversation_messages(
    database_url: str,
    conversation_id: str,
    *,
    limit: int = 200,
    encryption_key: str = "",
    decrypt: bool = True,
) -> list[InboxMessage]:
    """Return messages for one conversation hash."""
    ensure_schema(database_url)

    safe_limit = max(1, min(int(limit or 200), 500))
    safe_conversation_id = sanitize_untrusted_text(conversation_id, 128)

    if not safe_conversation_id:
        return []

    with _connect(database_url, dict_rows=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
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
                    AND sender_phone_hash = %s
                ORDER BY created_at ASC, id ASC
                LIMIT %s
                """,
                (safe_conversation_id, safe_limit),
            )
            rows = cur.fetchall()

    return [_row_to_inbox_message(row, encryption_key, decrypt=decrypt) for row in rows]


def list_opt_out_records(
    database_url: str,
    *,
    limit: int = 100,
) -> list[InboxOptOutRecord]:
    """Return recent opt-out records for the admin UI."""
    return store_opt_outs.list_opt_out_records(
        database_url,
        limit=limit,
        connect_factory=_connect,
        ensure_schema_func=ensure_schema,
    )


def get_dashboard_stats(database_url: str) -> InboxDashboardStats:
    """Return aggregate counters for the admin dashboard."""
    ensure_schema(database_url)

    with _connect(database_url, dict_rows=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS messages_total,
                    COUNT(*) FILTER (
                        WHERE created_at >= date_trunc('day', now())
                    ) AS messages_today,
                    COUNT(*) FILTER (
                        WHERE deleted_at IS NULL
                    ) AS messages_active,
                    COUNT(*) FILTER (
                        WHERE deleted_at IS NOT NULL
                    ) AS messages_deleted
                FROM inbox_messages
                """
            )
            message_row = cur.fetchone() or {}

            cur.execute("SELECT COUNT(*) AS total FROM inbox_opt_in_proofs")
            opt_in_row = cur.fetchone() or {}

            cur.execute("SELECT COUNT(*) AS total FROM inbox_opt_outs")
            opt_out_row = cur.fetchone() or {}

    return InboxDashboardStats(
        messages_total=int(message_row.get("messages_total") or 0),
        messages_today=int(message_row.get("messages_today") or 0),
        messages_active=int(message_row.get("messages_active") or 0),
        messages_deleted=int(message_row.get("messages_deleted") or 0),
        opt_in_proofs_total=int(opt_in_row.get("total") or 0),
        opt_outs_total=int(opt_out_row.get("total") or 0),
    )


def get_message_by_id(
    database_url: str,
    message_id: int,
    *,
    encryption_key: str = "",
    decrypt: bool = True,
) -> InboxMessage | None:
    """Return a single inbox message by primary key."""
    ensure_schema(database_url)

    with _connect(database_url, dict_rows=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
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
                WHERE id = %s
                LIMIT 1
                """,
                (message_id,),
            )
            row = cur.fetchone()

    if not row:
        return None

    return _row_to_inbox_message(row, encryption_key, decrypt=decrypt)


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
    store_audit.record_audit_event(
        database_url,
        actor=actor,
        actor_role=actor_role,
        action=action,
        target_message_id=target_message_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata=metadata,
        connect_factory=_connect,
        psycopg_modules=_psycopg_modules,
        ensure_schema_func=ensure_schema,
    )


# ─── Opt-out (LFPDPPP Oposición / CCPA) ────────────────────────────


MAX_STORED_OPT_OUT_KEYWORD_CHARS: Final = store_opt_outs.MAX_STORED_OPT_OUT_KEYWORD_CHARS
MAX_STORED_OPT_OUT_SOURCE_CHARS: Final = store_opt_outs.MAX_STORED_OPT_OUT_SOURCE_CHARS
MAX_STORED_LANGUAGE_CHARS: Final = store_opt_outs.MAX_STORED_LANGUAGE_CHARS


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
    return store_opt_outs.record_opt_out(
        database_url,
        sender_external_id=sender_external_id,
        sender_external_id_type=sender_external_id_type,
        source=source,
        keyword_used=keyword_used,
        language=language,
        encryption_key=encryption_key,
        proof_secret=proof_secret,
        connect_factory=_connect,
        ensure_schema_func=ensure_schema,
    )


def is_opted_out(database_url: str, sender_external_id: str) -> bool:
    """Return True when the sender (phone OR BSUID) has a recorded opt-out.

    Lookup is by external-id hash so phone and BSUID senders share one
    code path. The schema is ensured on first call per process; subsequent
    calls are a single indexed SELECT.
    """
    return store_opt_outs.is_opted_out(
        database_url,
        sender_external_id,
        connect_factory=_connect,
        ensure_schema_func=ensure_schema,
    )


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
    return store_opt_outs.delete_user_data(
        database_url,
        sender_external_id=sender_external_id,
        delete_opt_out_record=delete_opt_out_record,
        connect_factory=_connect,
        ensure_schema_func=ensure_schema,
    )
