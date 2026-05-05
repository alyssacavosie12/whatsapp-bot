"""Shared text normalization helpers."""

from __future__ import annotations

import re
import unicodedata


NON_WORD_RE = re.compile(r"[^a-z0-9\s%-]+")
SPACES_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-z0-9%-]+")
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def strip_accents(text: object) -> str:
    """Convert accented characters to lowercase plain ASCII equivalents."""
    value = str(text or "").lower().strip()

    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )


def normalize_text(text: object) -> str:
    """Normalize text for matching."""
    value = strip_accents(text)
    value = NON_WORD_RE.sub(" ", value)
    return SPACES_RE.sub(" ", value).strip()


def text_tokens(text: object) -> set[str]:
    """Return normalized word tokens."""
    return set(TOKEN_RE.findall(normalize_text(text)))


def sanitize_untrusted_text(text: object, max_length: int = 128) -> str:
    """Make untrusted display text safe for logs, prompts, and team alerts."""
    value = ANSI_ESCAPE_RE.sub("", str(text or ""))
    value = "".join(
        " " if unicodedata.category(char)[0] == "C" else char
        for char in value
    )
    value = value.replace("<", "").replace(">", "")
    value = SPACES_RE.sub(" ", value).strip()

    if len(value) <= max_length:
        return value

    return value[: max_length - 3].rstrip() + "..."
