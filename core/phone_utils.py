"""Phone number helpers for WhatsApp IDs."""

from __future__ import annotations

import re

VALID_PHONE_RE = re.compile(r"\d{10,15}")


def normalize_phone(phone: str) -> str:
    """Normalize Mexican WhatsApp numbers from 521XXXXXXXXXX to 52XXXXXXXXXX."""
    phone = str(phone or "").strip()

    if phone and phone.startswith("521") and len(phone) == 13:
        return "52" + phone[3:]

    return phone


def is_valid_phone(phone: str) -> bool:
    """Return True for E.164-like WhatsApp recipient numbers without a plus sign."""
    return bool(VALID_PHONE_RE.fullmatch(str(phone or "")))


def mask_phone(phone: str) -> str:
    """Mask a phone number for logs."""
    digits = "".join(char for char in str(phone or "") if char.isdigit())

    if len(digits) < 4:
        return "***"

    return f"***{digits[-4:]}"
