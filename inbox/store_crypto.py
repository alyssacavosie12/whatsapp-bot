"""Encryption and display helpers for inbox store fields."""

from __future__ import annotations

from typing import Any, cast

from core.text_utils import sanitize_untrusted_text
from inbox.store_common import (
    MAX_STORED_BODY_CHARS,
    MessageStoreUnavailable,
    _sha256,
)


def _fernet(encryption_key: str) -> Any | None:
    """Return a Fernet cipher when an inbox encryption key is configured."""
    if not encryption_key:
        return None

    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise MessageStoreUnavailable(
            "cryptography is required when INBOX_ENCRYPTION_KEY is set"
        ) from exc

    try:
        return Fernet(encryption_key.encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise MessageStoreUnavailable("INBOX_ENCRYPTION_KEY is invalid") from exc


def _prepare_body(body: object, encryption_key: str) -> tuple[str, bool, int, str]:
    """Sanitize, hash, and optionally encrypt a message body."""
    safe_body = sanitize_untrusted_text(body, MAX_STORED_BODY_CHARS)
    body_length = len(safe_body)
    body_sha256 = _sha256(safe_body)

    cipher = _fernet(encryption_key)
    if not cipher:
        return safe_body, False, body_length, body_sha256

    encrypted = cipher.encrypt(safe_body.encode("utf-8")).decode("utf-8")
    return encrypted, True, body_length, body_sha256


def _prepare_sensitive_field(
    value: object,
    max_chars: int,
    encryption_key: str,
) -> tuple[str, bool, str]:
    """Sanitize, hash, and optionally encrypt a sensitive text field."""
    safe_value = sanitize_untrusted_text(value, max_chars)
    value_hash = _sha256(safe_value)

    cipher = _fernet(encryption_key)
    if not cipher or not safe_value:
        return safe_value, False, value_hash

    encrypted = cipher.encrypt(safe_value.encode("utf-8")).decode("utf-8")
    return encrypted, True, value_hash


def _read_body(body: str, encrypted: bool, encryption_key: str) -> str:
    """Return a body plaintext or a clear unavailable marker."""
    if not encrypted:
        return body

    cipher = _fernet(encryption_key)
    if not cipher:
        return "[encrypted message unavailable: INBOX_ENCRYPTION_KEY is not set]"

    try:
        return cast(str, cipher.decrypt(body.encode("utf-8")).decode("utf-8"))
    except Exception:
        return "[encrypted message unavailable: decrypt failed]"


def _read_sensitive_field(
    value: str,
    encrypted: bool,
    encryption_key: str,
    *,
    fallback: str = "",
) -> str:
    """Return a sensitive plaintext field, or its safe fallback."""
    if not encrypted:
        return value

    cipher = _fernet(encryption_key)
    if not cipher:
        return fallback

    try:
        return cast(str, cipher.decrypt(value.encode("utf-8")).decode("utf-8"))
    except Exception:
        return fallback


def _body_for_display(
    body: str,
    encrypted: bool,
    encryption_key: str,
    *,
    decrypt: bool,
) -> str:
    """Return plaintext only when server-side decrypt is explicitly allowed."""
    if encrypted and not decrypt:
        return body

    return _read_body(body, encrypted, encryption_key)


def _sensitive_field_for_display(
    value: str,
    encrypted: bool,
    encryption_key: str,
    *,
    decrypt: bool,
    fallback: str = "",
) -> str:
    """Return sensitive plaintext only when server-side decrypt is allowed."""
    if encrypted and not decrypt:
        return fallback

    return _read_sensitive_field(
        value,
        encrypted,
        encryption_key,
        fallback=fallback,
    )
