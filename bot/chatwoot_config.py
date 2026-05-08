"""Chatwoot transport configuration checks."""

from __future__ import annotations

from typing import Final

from settings import (
    CHATWOOT_ACCOUNT_ID,
    CHATWOOT_API_TOKEN,
    CHATWOOT_TRANSPORT,
    CHATWOOT_WEBHOOK_SECRET,
)

__all__ = [
    "CHATWOOT_REQUIRED_ENV_VARS",
    "chatwoot_transport_misconfiguration",
]


CHATWOOT_REQUIRED_ENV_VARS: Final[tuple[str, ...]] = (
    "CHATWOOT_API_TOKEN",
    "CHATWOOT_ACCOUNT_ID",
    "CHATWOOT_WEBHOOK_SECRET",
)


def chatwoot_transport_misconfiguration() -> str | None:
    """Return a reason string when CHATWOOT_TRANSPORT is on but config is bad.

    Used by the Flask app factory to fail loudly at boot rather than
    discovering a missing env var on the first webhook delivery.
    """
    if not CHATWOOT_TRANSPORT:
        return None

    missing = []
    if not CHATWOOT_API_TOKEN:
        missing.append("CHATWOOT_API_TOKEN")
    if not CHATWOOT_ACCOUNT_ID:
        missing.append("CHATWOOT_ACCOUNT_ID")
    if not CHATWOOT_WEBHOOK_SECRET:
        missing.append("CHATWOOT_WEBHOOK_SECRET")

    if missing:
        return (
            "CHATWOOT_TRANSPORT is enabled but missing env vars: "
            f"{', '.join(missing)}"
        )

    return None