"""Admin inbox authentication, audit, and persistence orchestration."""

from __future__ import annotations

import hashlib
import hmac
import logging
from collections.abc import Callable
from threading import Thread
from typing import Any, Final

from flask import Response, request
from werkzeug.security import check_password_hash

from core.phone_utils import mask_phone
from inbox import store as inbox_store
from inbox.auth_throttle import (
    clear_inbox_auth_failures,
    inbox_auth_keys,
    is_inbox_auth_limited,
    record_inbox_auth_failure,
)
from inbox.compliance import build_inbound_opt_in_evidence
from inbox.security import admin_response, client_ip, inbox_auth_challenge
from settings import (
    INBOX_ADMIN_PASSWORD_HASH,
    INBOX_ADMIN_USERNAME,
    INBOX_CSRF_SECRET,
    INBOX_DATABASE_URL,
    INBOX_ENABLED,
    INBOX_ENCRYPTION_KEY,
    INBOX_PROOF_SECRET,
    INBOX_REQUIRE_ENCRYPTION,
    INBOX_RETENTION_DAYS,
    INBOX_VIEWER_PASSWORD_HASH,
    INBOX_VIEWER_USERNAME,
    META_APP_SECRET,
)

logger = logging.getLogger(__name__)

INBOX_ADMIN_ROLE: Final = "admin"
INBOX_VIEWER_ROLE: Final = "viewer"
INBOX_ROLES: Final[dict[str, int]] = {INBOX_VIEWER_ROLE: 1, INBOX_ADMIN_ROLE: 2}

InboxUser = dict[str, str]
InboxAuthResult = tuple[InboxUser | None, Response | None]
StoreTask = Callable[[str, str, str, str, object], None]


def inbox_configured() -> bool:
    """Return True when the admin inbox can use a database."""
    return bool(INBOX_ENABLED and INBOX_DATABASE_URL)


def inbox_auth_configured() -> bool:
    """Return True when at least one admin inbox user is configured."""
    return bool(
        (INBOX_ADMIN_USERNAME and INBOX_ADMIN_PASSWORD_HASH)
        or (INBOX_VIEWER_USERNAME and INBOX_VIEWER_PASSWORD_HASH)
    )


def inbox_encryption_configured() -> bool:
    """Return True when inbox storage satisfies encryption policy."""
    return bool(not INBOX_REQUIRE_ENCRYPTION or INBOX_ENCRYPTION_KEY)


def role_allows(user_role: str, required_role: str) -> bool:
    """Return True when a user's inbox role satisfies a required role."""
    return INBOX_ROLES.get(user_role, 0) >= INBOX_ROLES.get(required_role, 0)


def get_inbox_users() -> list[InboxUser]:
    """Build configured admin inbox users from environment variables."""
    users = []

    if INBOX_ADMIN_USERNAME and INBOX_ADMIN_PASSWORD_HASH:
        users.append(
            {
                "username": INBOX_ADMIN_USERNAME,
                "password_hash": INBOX_ADMIN_PASSWORD_HASH,
                "role": INBOX_ADMIN_ROLE,
            }
        )

    if INBOX_VIEWER_USERNAME and INBOX_VIEWER_PASSWORD_HASH:
        users.append(
            {
                "username": INBOX_VIEWER_USERNAME,
                "password_hash": INBOX_VIEWER_PASSWORD_HASH,
                "role": INBOX_VIEWER_ROLE,
            }
        )

    return users


def authenticate_inbox_user() -> InboxUser | None:
    """Authenticate the current request using HTTP Basic auth."""
    auth = request.authorization

    if not auth or not auth.username or auth.password is None:
        return None

    for user in get_inbox_users():
        if not hmac.compare_digest(auth.username, user["username"]):
            continue

        try:
            password_ok = check_password_hash(
                user["password_hash"],
                auth.password,
            )
        except ValueError:
            logger.error("Invalid inbox password hash for user role=%s", user["role"])
            return None

        if password_ok:
            return {"username": user["username"], "role": user["role"]}

    return None


def require_inbox_user(required_role: str = INBOX_VIEWER_ROLE) -> InboxAuthResult:
    """Return the authenticated inbox user or a response to send back."""
    if not inbox_configured():
        return None, admin_response("Inbox is not configured", 503)

    if not inbox_encryption_configured():
        return None, admin_response("Inbox encryption is not configured", 503)

    if not inbox_auth_configured():
        return None, admin_response("Inbox authentication is not configured", 503)

    auth = request.authorization
    auth_username = auth.username if auth and auth.username else ""
    throttle_keys = inbox_auth_keys(client_ip(), auth_username)

    if is_inbox_auth_limited(throttle_keys):
        return None, admin_response("Too many failed login attempts", 429)

    user = authenticate_inbox_user()
    if not user:
        if auth and auth.username:
            record_inbox_auth_failure(throttle_keys)
        return None, inbox_auth_challenge()

    clear_inbox_auth_failures(throttle_keys)

    if not role_allows(user["role"], required_role):
        return None, admin_response("Forbidden", 403)

    return user, None


def csrf_secret() -> str:
    """Return the secret used to protect state-changing admin forms."""
    return INBOX_CSRF_SECRET or META_APP_SECRET


def inbox_proof_secret() -> str:
    """Return the secret used to HMAC opt-in proof records."""
    return INBOX_PROOF_SECRET or INBOX_CSRF_SECRET or META_APP_SECRET


def inbox_csrf_token(username: str, action: str, target_id: int) -> str:
    """Build a stable HMAC token for an admin inbox form action."""
    secret = csrf_secret()
    if not secret:
        return ""

    payload = f"{username}:{action}:{target_id}".encode()
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def valid_inbox_csrf(username: str, action: str, target_id: int) -> bool:
    """Validate a submitted admin inbox CSRF token."""
    expected = inbox_csrf_token(username, action, target_id)
    submitted = request.form.get("csrf_token", "")

    return bool(expected and hmac.compare_digest(expected, submitted))


def audit_inbox_action(
    user: InboxUser,
    action: str,
    *,
    target_message_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write an inbox audit event without leaking message content to logs."""
    if not inbox_configured():
        return

    try:
        inbox_store.record_audit_event(
            INBOX_DATABASE_URL,
            actor=user["username"],
            actor_role=user["role"],
            action=action,
            target_message_id=target_message_id,
            ip_address=client_ip(),
            user_agent=request.headers.get("User-Agent", ""),
            metadata=metadata or {},
        )
    except Exception as exc:
        logger.error("Failed to record inbox audit event: %s", exc.__class__.__name__)


def run_store_in_background(
    target: StoreTask,
    message_id: str,
    sender_phone: str,
    sender_name: str,
    message_type: str,
    body: object,
) -> None:
    """Run inbox persistence without blocking the bot response path."""
    Thread(
        target=target,
        args=(message_id, sender_phone, sender_name, message_type, body),
        daemon=True,
    ).start()


def _store_incoming_message(
    message_id: str,
    sender_phone: str,
    sender_name: str,
    message_type: str,
    body: object,
) -> None:
    """Persist an inbound message for the admin inbox when configured."""
    if not inbox_configured():
        return

    if not inbox_encryption_configured():
        logger.error("Inbox encryption is required; incoming message was not stored")
        return

    try:
        from core.sender_id import mask_sender_id, parse_sender_id

        parsed_sender = parse_sender_id(sender_phone)
        masked_sender = mask_sender_id(parsed_sender) if parsed_sender else mask_phone(sender_phone)

        inbox_store.record_incoming_message(
            INBOX_DATABASE_URL,
            whatsapp_message_id=message_id,
            sender_phone=sender_phone,
            sender_phone_masked=masked_sender,
            sender_name=sender_name,
            message_type=message_type,
            body=body,
            encryption_key=INBOX_ENCRYPTION_KEY,
            retention_days=INBOX_RETENTION_DAYS,
        )
        inbox_store.record_opt_in_proof(
            INBOX_DATABASE_URL,
            whatsapp_message_id=message_id,
            sender_phone=sender_phone,
            proof_type="inbound_customer_initiated",
            proof_source="whatsapp_webhook",
            evidence=build_inbound_opt_in_evidence(
                message_id,
                sender_phone,
                message_type,
                body,
            ),
            proof_secret=inbox_proof_secret(),
            encryption_key=INBOX_ENCRYPTION_KEY,
        )
    except Exception as exc:
        logger.error("Failed to store incoming message: %s", exc.__class__.__name__)


def store_incoming_message(
    message_id: str,
    sender_phone: str,
    sender_name: str,
    message_type: str,
    body: object,
) -> None:
    """Queue inbound message persistence without blocking customer replies."""
    run_store_in_background(
        _store_incoming_message,
        message_id,
        sender_phone,
        sender_name,
        message_type,
        body,
    )


def is_first_contact(sender_external_id: str) -> bool:
    """Return True when this sender has no prior inbound inbox history.

    If the inbox database is unavailable, fail toward showing the Privacy
    Notice. Repeating the notice is preferable to silently omitting it.
    """
    if not inbox_configured():
        return True

    try:
        return not inbox_store.has_incoming_message_for_sender(
            INBOX_DATABASE_URL,
            sender_external_id,
        )
    except Exception as exc:
        logger.error(
            "first_contact_check_failed sender=%s error=%s",
            mask_phone(sender_external_id),
            exc.__class__.__name__,
        )
        return True


# ─── Opt-out (LFPDPPP Oposición / CCPA) ───────────────────────────────


def is_opted_out(sender_external_id: str) -> bool:
    """Return True when the sender (phone OR BSUID) has a recorded opt-out.

    Fails open on database error: a Postgres outage must not silence every
    customer. The error path is logged so any opted-out user reached during
    an outage can be reconciled from logs.
    """
    if not inbox_configured():
        return False

    try:
        return inbox_store.is_opted_out(INBOX_DATABASE_URL, sender_external_id)
    except Exception as exc:
        logger.error(
            "opt_out_check_failed sender=%s error=%s",
            mask_phone(sender_external_id),
            exc.__class__.__name__,
        )
        return False


def record_opt_out(
    sender_external_id: str,
    *,
    sender_external_id_type: str = "phone",
    source: str,
    keyword_used: str = "",
    language: str = "",
) -> bool:
    """Record an opt-out request. Returns True if newly inserted, False if duplicate.

    Idempotent on the external-id hash so a second STOP from the same user
    (phone or BSUID) does not duplicate the row. Failures are logged but
    not raised — the webhook handler must stay up even if inbox storage is
    temporarily unavailable.
    """
    if not inbox_configured():
        logger.warning(
            "opt_out_recorded_without_db sender=%s source=%s",
            mask_phone(sender_external_id),
            source,
        )
        return False

    try:
        return inbox_store.record_opt_out(
            INBOX_DATABASE_URL,
            sender_external_id=sender_external_id,
            sender_external_id_type=sender_external_id_type,
            source=source,
            keyword_used=keyword_used,
            language=language,
            encryption_key=INBOX_ENCRYPTION_KEY,
            proof_secret=inbox_proof_secret(),
        )
    except Exception as exc:
        logger.error(
            "opt_out_record_failed sender=%s error=%s",
            mask_phone(sender_external_id),
            exc.__class__.__name__,
        )
        return False


def delete_user_data(
    sender_external_id: str,
    *,
    delete_opt_out_record: bool = False,
) -> dict[str, int]:
    """Delete all stored records for one user (ARCO Cancelación).

    Accepts either an E.164 phone or a BSUID.
    """
    if not inbox_configured():
        raise RuntimeError("Inbox is not configured")

    return inbox_store.delete_user_data(
        INBOX_DATABASE_URL,
        sender_external_id=sender_external_id,
        delete_opt_out_record=delete_opt_out_record,
    )
