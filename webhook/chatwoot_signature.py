"""HMAC verification for Chatwoot agent-bot webhooks.

Chatwoot signs each agent-bot webhook delivery with HMAC-SHA256 over the raw
request body using the bot's webhook secret. The signature is sent in the
``X-Chatwoot-Signature`` header as a hex digest (no ``sha256=`` prefix).
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from flask import request

from settings import CHATWOOT_WEBHOOK_SECRET

logger = logging.getLogger(__name__)


def verify_chatwoot_signature() -> bool:
    """Verify ``X-Chatwoot-Signature`` for the current Flask request.

    Returns True only when a non-empty secret is configured AND the signature
    matches the body's HMAC-SHA256 hex digest. Missing secret means we refuse
    the webhook (fail-closed) rather than accept unsigned events.
    """
    if not CHATWOOT_WEBHOOK_SECRET:
        logger.error("CHATWOOT_WEBHOOK_SECRET is not set; refusing Chatwoot webhook")
        return False

    signature = request.headers.get("X-Chatwoot-Signature", "").strip()
    if not signature:
        logger.warning("Missing X-Chatwoot-Signature header")
        return False

    raw_body = request.get_data(cache=True)
    expected = hmac.new(
        CHATWOOT_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected.encode("utf-8"), signature.encode("utf-8"))
