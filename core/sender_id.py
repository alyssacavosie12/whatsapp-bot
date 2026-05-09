"""Identify the originator of a WhatsApp webhook message.

Meta's June 2026 rollout of Business-Scoped User IDs lets users hide their
phone number, in which case the webhook payload's ``message.from`` is a
BSUID instead of an E.164 phone. The bot still has to:
- Accept the message (today's `is_valid_phone` check would drop it).
- Track opt-out and conversation state by a stable per-user key.
- Send replies back to whatever id Meta gave us.

This module provides a single canonical id with a discriminator so callers
don't have to special-case the two flavours throughout the code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

from core.phone_utils import is_valid_phone, normalize_phone

SenderIdType = Literal["phone", "bsuid"]

# BSUID is opaque to us. Meta hasn't published an exact format, so we accept
# anything that's clearly an identifier (8-128 ASCII URL-safe chars) and not
# already a valid E.164 number.
_BSUID_RE: Final = re.compile(r"\A[A-Za-z0-9._:\-]{8,128}\Z")


@dataclass(frozen=True)
class SenderId:
    """Canonical identifier for the sender of one webhook message."""

    value: str
    """The canonical id string — normalized phone or raw BSUID."""

    id_type: SenderIdType
    """Discriminator: 'phone' for E.164, 'bsuid' for opaque user id."""

    @property
    def is_phone(self) -> bool:
        """Return True when this id is a phone number."""
        return self.id_type == "phone"

    @property
    def is_bsuid(self) -> bool:
        """Return True when this id is a Business-Scoped User ID."""
        return self.id_type == "bsuid"


def parse_sender_id(raw: str) -> SenderId | None:
    """Return a parsed sender id, or None for unrecognized input.

    Phone numbers are normalized (Mexican 521... -> 52... rule from
    `core.phone_utils.normalize_phone`); BSUIDs are returned verbatim.
    """
    if not raw:
        return None

    candidate = raw.strip()
    if not candidate:
        return None

    normalized = normalize_phone(candidate)
    if normalized and is_valid_phone(normalized):
        return SenderId(value=normalized, id_type="phone")

    if _BSUID_RE.fullmatch(candidate):
        return SenderId(value=candidate, id_type="bsuid")

    return None


def is_valid_recipient(value: str) -> bool:
    """Return True when `value` is something we can address via Graph API.

    Used by the WhatsApp client to gate outbound sends. Mirrors
    `parse_sender_id` but returns a bool for ergonomics in the send path.
    """
    return parse_sender_id(value) is not None


def mask_sender_id(sender: SenderId) -> str:
    """Return a privacy-preserving representation for logs.

    For phones, defers to `core.phone_utils.mask_phone`. For BSUIDs, keeps
    the type prefix and the last 4 chars.
    """
    if sender.is_phone:
        from core.phone_utils import mask_phone

        return mask_phone(sender.value)

    return f"bsuid:***{sender.value[-4:]}" if len(sender.value) >= 4 else "bsuid:***"
