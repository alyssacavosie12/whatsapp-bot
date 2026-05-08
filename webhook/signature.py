"""Meta webhook signature verification."""

from __future__ import annotations

import hashlib
import hmac
import logging

from flask import request

from settings import META_APP_SECRET

logger = logging.getLogger(__name__)


def verify_meta_signature() -> bool:
    """Verify Meta X-Hub-Signature-256 for POST webhooks. Always required."""
    if not META_APP_SECRET:
        logger.error("META_APP_SECRET is not set; refusing webhook")
        return False

    signature = request.headers.get("X-Hub-Signature-256", "")

    if not signature.startswith("sha256="):
        logger.warning("Missing or invalid X-Hub-Signature-256 header")
        return False

    raw_body = request.get_data(cache=True)
    expected = (
        "sha256="
        + hmac.new(
            META_APP_SECRET.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(expected, signature)
