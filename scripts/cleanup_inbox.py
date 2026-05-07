"""Delete expired inbox data outside the webhook hot path."""

from __future__ import annotations

import logging

from inbox.store import cleanup_expired_messages
from settings import INBOX_DATABASE_URL, INBOX_RETENTION_DAYS

logger = logging.getLogger(__name__)


def main() -> int:
    """Run inbox retention cleanup once."""
    if not INBOX_DATABASE_URL:
        logger.error("DATABASE_URL is not configured")
        return 1

    deleted = cleanup_expired_messages(INBOX_DATABASE_URL, INBOX_RETENTION_DAYS)
    logger.warning("Deleted %s expired inbox messages", deleted)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    raise SystemExit(main())
