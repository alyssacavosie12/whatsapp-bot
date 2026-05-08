"""Opt-in proof persistence for the admin inbox."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable
from typing import Any

from core.text_utils import sanitize_untrusted_text
from inbox.store_common import (
    MAX_STORED_BODY_CHARS,
    MAX_STORED_MESSAGE_ID_CHARS,
    MAX_STORED_PHONE_CHARS,
    MAX_STORED_TYPE_CHARS,
    MessageStoreUnavailable,
    _connect,
)
from inbox.store_crypto import _prepare_sensitive_field
from inbox.store_schema import ensure_schema

ConnectFactory = Callable[..., Any]


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
    connect_factory: ConnectFactory = _connect,
    ensure_schema_func: Callable[[str], None] = ensure_schema,
) -> None:
    """Store a tamper-evident proof that the user initiated the conversation."""
    if not proof_secret:
        raise MessageStoreUnavailable("INBOX_PROOF_SECRET is not configured")

    ensure_schema_func(database_url)

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

    with connect_factory(database_url) as conn:
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
