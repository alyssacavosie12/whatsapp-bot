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

CHATWOOT_ENV_VALUES: Final[dict[str, object]] = {
    "CHATWOOT_API_TOKEN": CHATWOOT_API_TOKEN,
    "CHATWOOT_ACCOUNT_ID": CHATWOOT_ACCOUNT_ID,
    "CHATWOOT_WEBHOOK_SECRET": CHATWOOT_WEBHOOK_SECRET,
}


def chatwoot_transport_misconfiguration() -> str | None:
    """Return a reason string when CHATWOOT_TRANSPORT is on but config is bad.

    Used by the Flask app factory to fail loudly at boot rather than
    discovering a missing env var on the first webhook delivery.

    Example:
        reason = chatwoot_transport_misconfiguration()
        if reason:
            raise RuntimeError(reason)
    """
    if not CHATWOOT_TRANSPORT:
        return None

    missing = [name for name in CHATWOOT_REQUIRED_ENV_VARS if not CHATWOOT_ENV_VALUES.get(name)]

    if missing:
        return f"CHATWOOT_TRANSPORT is enabled but missing env vars: {', '.join(missing)}"

    return None
