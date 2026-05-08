"""Delete expired inbox data outside the webhook hot path."""

from __future__ import annotations

import logging
from typing import Final

from inbox.store import cleanup_expired_messages, record_audit_event
from settings import INBOX_DATABASE_URL, INBOX_RETENTION_DAYS

logger = logging.getLogger(__name__)

RETENTION_CLEANUP_ACTOR: Final = "system:retention-cleanup"


def main() -> int:
    """Run inbox retention cleanup once."""
    if not INBOX_DATABASE_URL:
        logger.error("DATABASE_URL is not configured")
        return 1

    try:
        deleted = cleanup_expired_messages(INBOX_DATABASE_URL, INBOX_RETENTION_DAYS)
        record_audit_event(
            INBOX_DATABASE_URL,
            actor=RETENTION_CLEANUP_ACTOR,
            actor_role="system",
            action="retention_cleanup",
            metadata={
                "deleted_messages": deleted,
                "retention_days": INBOX_RETENTION_DAYS,
            },
        )
    except Exception as exc:
        logger.error("Inbox retention cleanup failed: %s", exc.__class__.__name__)
        return 1

    logger.warning(
        "Deleted %s expired inbox messages; retention_days=%s",
        deleted,
        INBOX_RETENTION_DAYS,
    )
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    raise SystemExit(main())
