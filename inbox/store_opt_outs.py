"""Opt-out and data-subject deletion persistence for the admin inbox."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable
from typing import Any, Final

from core.text_utils import sanitize_untrusted_text
from inbox.store_common import (
    MAX_STORED_PHONE_CHARS,
    MessageStoreUnavailable,
    _connect,
    _sha256,
)
from inbox.store_models import InboxOptOutRecord
from inbox.store_schema import ensure_schema

MAX_STORED_OPT_OUT_KEYWORD_CHARS: Final = 64
MAX_STORED_OPT_OUT_SOURCE_CHARS: Final = 32
MAX_STORED_LANGUAGE_CHARS: Final = 8

ConnectFactory = Callable[..., Any]


def list_opt_out_records(
    database_url: str,
    *,
    limit: int = 100,
    connect_factory: ConnectFactory = _connect,
    ensure_schema_func: Callable[[str], None] = ensure_schema,
) -> list[InboxOptOutRecord]:
    """Return recent opt-out records for the admin UI."""
    ensure_schema_func(database_url)

    safe_limit = max(1, min(int(limit or 100), 500))

    with connect_factory(database_url, dict_rows=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    sender_external_id_hash,
                    sender_external_id_type,
                    source,
                    keyword_used,
                    language,
                    recorded_at
                FROM inbox_opt_outs
                ORDER BY recorded_at DESC
                LIMIT %s
                """,
                (safe_limit,),
            )
            rows = cur.fetchall()

    return [
        InboxOptOutRecord(
            id=row["id"],
            sender_external_id_hash=row["sender_external_id_hash"] or "",
            sender_external_id_type=row["sender_external_id_type"] or "",
            source=row["source"] or "",
            keyword_used=row["keyword_used"] or "",
            language=row["language"] or "",
            recorded_at=row["recorded_at"],
        )
        for row in rows
    ]


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
    connect_factory: ConnectFactory = _connect,
    ensure_schema_func: Callable[[str], None] = ensure_schema,
) -> bool:
    """Record an opt-out request. Returns True if newly inserted."""
    del encryption_key

    if not proof_secret:
        raise MessageStoreUnavailable("INBOX_PROOF_SECRET is not configured")
    if not sender_external_id:
        raise MessageStoreUnavailable("Cannot record opt-out without an external id")

    ensure_schema_func(database_url)

    safe_external_id = sanitize_untrusted_text(sender_external_id, MAX_STORED_PHONE_CHARS)
    external_id_hash = _sha256(safe_external_id)
    if not external_id_hash:
        raise MessageStoreUnavailable("Cannot record opt-out for an empty external id")

    safe_external_id_type = sanitize_untrusted_text(
        sender_external_id_type, MAX_STORED_LANGUAGE_CHARS
    )
    if safe_external_id_type not in {"phone", "bsuid"}:
        safe_external_id_type = "phone"

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

    with connect_factory(database_url) as conn:
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
                    None,
                    None,
                    False,
                    None,
                    safe_external_id_type,
                    external_id_hash,
                    safe_source,
                    safe_keyword,
                    safe_language,
                    evidence_hmac,
                ),
            )
            return int(cur.rowcount or 0) > 0


def is_opted_out(
    database_url: str,
    sender_external_id: str,
    *,
    connect_factory: ConnectFactory = _connect,
    ensure_schema_func: Callable[[str], None] = ensure_schema,
) -> bool:
    """Return True when the sender has a recorded opt-out."""
    if not sender_external_id:
        return False

    external_id_hash = _sha256(sanitize_untrusted_text(sender_external_id, MAX_STORED_PHONE_CHARS))
    if not external_id_hash:
        return False

    ensure_schema_func(database_url)

    with connect_factory(database_url) as conn:
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
    connect_factory: ConnectFactory = _connect,
    ensure_schema_func: Callable[[str], None] = ensure_schema,
) -> dict[str, int]:
    """Delete personal data for one user while preserving minimal legal proof.

    ARCO/CCPA-style cancellation removes inbox messages and opt-in proof linked
    to the sender. By default, the opt-out record is retained in minimized form:
    plaintext identifiers are cleared, legacy phone fields are nulled, and the
    hashed external id plus HMAC evidence remain so the clinic can prove it
    honored the user's opposition/non-consent request.

    Pass ``delete_opt_out_record=True`` only when the user explicitly requests
    deletion of the opt-out proof too and accepts that future inbound messages
    may be treated as a new contact.
    """
    if not sender_external_id:
        raise MessageStoreUnavailable("Cannot delete data for an empty id")

    safe_external_id = sanitize_untrusted_text(sender_external_id, MAX_STORED_PHONE_CHARS)
    external_id_hash = _sha256(safe_external_id)
    if not external_id_hash:
        raise MessageStoreUnavailable("Cannot delete data for an empty id")

    ensure_schema_func(database_url)

    counts: dict[str, int] = {}
    with connect_factory(database_url) as conn:
        with conn.cursor() as cur:
            # Hard-delete user-controlled message content and contact fields.
            cur.execute(
                "DELETE FROM inbox_messages WHERE sender_phone_hash = %s",
                (external_id_hash,),
            )
            counts["messages"] = int(cur.rowcount or 0)

            # Hard-delete opt-in evidence because it can contain user/contact
            # metadata. Opt-out evidence is handled separately below.
            cur.execute(
                "DELETE FROM inbox_opt_in_proofs WHERE sender_phone_hash = %s",
                (external_id_hash,),
            )
            counts["opt_in_proofs"] = int(cur.rowcount or 0)

            if delete_opt_out_record:
                # Full deletion: future inbound messages from this sender will
                # no longer be blocked by this stored opt-out proof.
                cur.execute(
                    """
                    DELETE FROM inbox_opt_outs
                    WHERE sender_external_id_hash = %s
                    """,
                    (external_id_hash,),
                )
                counts["opt_outs"] = int(cur.rowcount or 0)
            else:
                # Data-minimized retention: keep only what is needed to honor
                # the opposition request and demonstrate compliance.
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
