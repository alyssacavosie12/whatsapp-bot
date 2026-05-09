"""Admin conversation route handlers."""

from __future__ import annotations

import logging
from typing import Final

from flask import request
from flask.typing import ResponseReturnValue

from inbox import service as inbox_service
from inbox import store as inbox_store
from inbox.admin_pages import (
    render_admin_conversation_detail_page,
    render_admin_conversations_page,
    short_hash,
    valid_hash_id,
)
from inbox.security import admin_response
from inbox.store_common import STORE_OPERATION_ERRORS

logger = logging.getLogger(__name__)

DEFAULT_CONVERSATION_LIMIT: Final = 100
MAX_CONVERSATION_LIMIT: Final = 500
DEFAULT_CONVERSATION_MESSAGE_LIMIT: Final = 200
MAX_CONVERSATION_MESSAGE_LIMIT: Final = 500

__all__ = [
    "admin_conversation_detail",
    "admin_conversations",
]


def _query_limit(
    *,
    name: str = "limit",
    default: int,
    maximum: int,
) -> int:
    """Return a safely clamped integer limit from query parameters."""
    raw_limit = request.args.get(name, "")

    try:
        parsed = int(raw_limit)
    except (TypeError, ValueError):
        return default

    return max(1, min(parsed, maximum))


def admin_conversations() -> ResponseReturnValue:
    """Show recent conversation summaries.

    Supports optional ``?limit=`` query parameter for lightweight scaling
    without changing page templates.
    """
    user, error_response = inbox_service.require_inbox_user(inbox_service.INBOX_VIEWER_ROLE)
    if error_response:
        return error_response
    if user is None:
        return admin_response("Unauthorized", 401)

    limit = _query_limit(
        default=DEFAULT_CONVERSATION_LIMIT,
        maximum=MAX_CONVERSATION_LIMIT,
    )

    try:
        conversations = inbox_store.list_conversations(
            inbox_service.inbox_database_url(),
            limit=limit,
            encryption_key=inbox_service.inbox_encryption_key(),
            decrypt=False,
        )
    except STORE_OPERATION_ERRORS:
        logger.exception("Failed to load admin conversations")
        return admin_response("Conversations are unavailable", 503)

    inbox_service.audit_inbox_action(
        user,
        "view_conversations",
        metadata={
            "limit": limit,
            "result_count": len(conversations),
        },
    )

    return admin_response(render_admin_conversations_page(user, conversations))


def admin_conversation_detail(conversation_id: str) -> ResponseReturnValue:
    """Show one conversation.

    Supports optional ``?limit=`` query parameter to cap loaded messages.
    """
    user, error_response = inbox_service.require_inbox_user(inbox_service.INBOX_VIEWER_ROLE)
    if error_response:
        return error_response
    if user is None:
        return admin_response("Unauthorized", 401)

    if not valid_hash_id(conversation_id):
        return admin_response("Conversation not found", 404)

    limit = _query_limit(
        default=DEFAULT_CONVERSATION_MESSAGE_LIMIT,
        maximum=MAX_CONVERSATION_MESSAGE_LIMIT,
    )

    try:
        messages = inbox_store.get_conversation_messages(
            inbox_service.inbox_database_url(),
            conversation_id,
            limit=limit,
            encryption_key=inbox_service.inbox_encryption_key(),
            decrypt=False,
        )
    except STORE_OPERATION_ERRORS:
        logger.exception("Failed to load admin conversation")
        return admin_response("Conversation is unavailable", 503)

    if not messages:
        return admin_response("Conversation not found", 404)

    inbox_service.audit_inbox_action(
        user,
        "view_conversation",
        metadata={
            "conversation_id": short_hash(conversation_id),
            "limit": limit,
            "message_count": len(messages),
        },
    )

    return admin_response(render_admin_conversation_detail_page(user, conversation_id, messages))
