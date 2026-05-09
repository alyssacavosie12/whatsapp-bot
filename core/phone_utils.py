"""Phone number helpers for WhatsApp IDs."""

from __future__ import annotations

import re
from typing import Final

# E.164 allows up to 15 digits and does not allow a leading zero.
VALID_PHONE_RE: Final = re.compile(r"[1-9]\d{9,14}")

__all__ = [
    "is_valid_phone",
    "mask_phone",
    "normalize_phone",
]


def normalize_phone(phone: str) -> str:
    """Return a digit-only WhatsApp phone id.

    Normalization:
    - removes non-digit formatting such as ``+``, spaces, and dashes;
    - normalizes Mexican WhatsApp numbers from ``521XXXXXXXXXX`` to
      ``52XXXXXXXXXX``.

    Business-Scoped User IDs are not phone numbers and should be handled by
    ``core.sender_id.parse_sender_id`` rather than this helper.
    """
    digits = "".join(char for char in str(phone or "").strip() if char.isdigit())

    if digits.startswith("521") and len(digits) == 13:
        return "52" + digits[3:]

    return digits


def is_valid_phone(phone: str) -> bool:
    """Return True for E.164-like WhatsApp recipient numbers without a plus sign."""
    return bool(VALID_PHONE_RE.fullmatch(str(phone or "")))


def mask_phone(phone: str) -> str:
    """Mask a phone number for logs."""
    digits = "".join(char for char in str(phone or "") if char.isdigit())

    if len(digits) < 4:
        return "***"

    return f"***{digits[-4:]}"
