"""Admin conversation route handlers."""

from __future__ import annotations

import logging

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

logger = logging.getLogger(__name__)


def admin_conversations() -> ResponseReturnValue:
    """Show conversation summaries."""
    user, error_response = inbox_service.require_inbox_user(inbox_service.INBOX_VIEWER_ROLE)
    if error_response:
        return error_response
    if user is None:
        return admin_response("Unauthorized", 401)

    try:
        conversations = inbox_store.list_conversations(
            inbox_service.inbox_database_url(),
            encryption_key=inbox_service.inbox_encryption_key(),
            decrypt=False,
        )
    except Exception:
        logger.exception("Failed to load admin conversations")
        return admin_response("Conversations are unavailable", 503)

    inbox_service.audit_inbox_action(
        user,
        "view_conversations",
        metadata={"result_count": len(conversations)},
    )

    return admin_response(render_admin_conversations_page(user, conversations))


def admin_conversation_detail(conversation_id: str) -> ResponseReturnValue:
    """Show one conversation."""
    user, error_response = inbox_service.require_inbox_user(inbox_service.INBOX_VIEWER_ROLE)
    if error_response:
        return error_response
    if user is None:
        return admin_response("Unauthorized", 401)

    if not valid_hash_id(conversation_id):
        return admin_response("Conversation not found", 404)

    try:
        messages = inbox_store.get_conversation_messages(
            inbox_service.inbox_database_url(),
            conversation_id,
            encryption_key=inbox_service.inbox_encryption_key(),
            decrypt=False,
        )
    except Exception:
        logger.exception("Failed to load admin conversation")
        return admin_response("Conversation is unavailable", 503)

    if not messages:
        return admin_response("Conversation not found", 404)

    inbox_service.audit_inbox_action(
        user,
        "view_conversation",
        metadata={
            "conversation_id": short_hash(conversation_id),
            "message_count": len(messages),
        },
    )

    return admin_response(render_admin_conversation_detail_page(user, conversation_id, messages))
