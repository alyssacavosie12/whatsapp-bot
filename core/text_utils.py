"""Shared text normalization helpers."""

from __future__ import annotations

import re
import unicodedata
from typing import Final

NON_WORD_RE: Final = re.compile(r"[^a-z0-9\s%-]+")
SPACES_RE: Final = re.compile(r"\s+")
TOKEN_RE: Final = re.compile(r"[a-z0-9%-]+")
ANSI_ESCAPE_RE: Final = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

DEFAULT_SANITIZED_TEXT_MAX_LENGTH: Final = 128
TRUNCATION_SUFFIX: Final = "..."

__all__ = [
    "ANSI_ESCAPE_RE",
    "DEFAULT_SANITIZED_TEXT_MAX_LENGTH",
    "NON_WORD_RE",
    "SPACES_RE",
    "TOKEN_RE",
    "normalize_text",
    "sanitize_untrusted_text",
    "strip_accents",
    "text_tokens",
]


def strip_accents(text: object) -> str:
    """Convert accented characters to lowercase plain ASCII equivalents."""
    value = str(text or "").lower().strip()

    return "".join(
        char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char)
    )


def normalize_text(text: object) -> str:
    """Normalize text for matching."""
    value = strip_accents(text)
    value = NON_WORD_RE.sub(" ", value)
    return SPACES_RE.sub(" ", value).strip()


def text_tokens(text: object) -> set[str]:
    """Return normalized word tokens."""
    return set(TOKEN_RE.findall(normalize_text(text)))


def sanitize_untrusted_text(
    text: object,
    max_length: int = DEFAULT_SANITIZED_TEXT_MAX_LENGTH,
) -> str:
    """Make untrusted display text safe for logs, prompts, and team alerts.

    Raw customer-controlled text should not be sent to logs, team alerts, or
    model prompts unless the caller has intentionally chosen the destination
    and applied the appropriate sanitization/redaction.
    """
    value = ANSI_ESCAPE_RE.sub("", str(text or ""))
    value = "".join(" " if unicodedata.category(char)[0] == "C" else char for char in value)
    value = value.replace("<", "").replace(">", "")
    value = SPACES_RE.sub(" ", value).strip()

    if max_length <= len(TRUNCATION_SUFFIX):
        return value[:max_length]

    if len(value) <= max_length:
        return value

    return value[: max_length - len(TRUNCATION_SUFFIX)].rstrip() + TRUNCATION_SUFFIX
