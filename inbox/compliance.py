"""Compliance-oriented helpers for WhatsApp message records."""

from __future__ import annotations

import hashlib

from core.text_utils import sanitize_untrusted_text


def build_inbound_opt_in_evidence(
    message_id: str,
    sender_phone: str,
    message_type: str,
    body: object,
) -> dict[str, str | int]:
    """Build non-plaintext evidence for an inbound customer-initiated message."""
    body_text = str(body or "")
    return {
        "event": "inbound_whatsapp_message",
        "message_id": sanitize_untrusted_text(message_id, 128),
        "message_type": sanitize_untrusted_text(message_type, 32),
        "sender_phone_hash": hashlib.sha256(str(sender_phone or "").encode("utf-8")).hexdigest(),
        "body_sha256": hashlib.sha256(body_text.encode("utf-8")).hexdigest(),
        "body_length": len(body_text),
    }
