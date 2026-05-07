"""Admin inbox routes."""

from __future__ import annotations

import logging

from flask import Flask, redirect, request, url_for
from flask.typing import ResponseReturnValue

from inbox import service as inbox_service
from inbox import store as inbox_store
from inbox.security import admin_response
from inbox.views import render_admin_messages_page
from settings import INBOX_DATABASE_URL, INBOX_ENCRYPTION_KEY

logger = logging.getLogger(__name__)


def register_admin_routes(flask_app: Flask) -> None:
    """Attach /admin/messages and the soft-delete handler to the given Flask app."""

    @flask_app.route("/admin/messages", methods=["GET"])
    def admin_messages() -> ResponseReturnValue:
        """Show recent incoming WhatsApp messages to authorized users."""
        user, error_response = inbox_service.require_inbox_user(inbox_service.INBOX_VIEWER_ROLE)
        if error_response:
            return error_response
        if user is None:
            return admin_response("Unauthorized", 401)

        query = request.args.get("q", "").strip()

        try:
            limit = int(request.args.get("limit", "100"))
        except ValueError:
            limit = 100

        limit = max(1, min(limit, 500))

        try:
            messages = inbox_store.list_messages(
                INBOX_DATABASE_URL,
                query=query,
                limit=limit,
                encryption_key=INBOX_ENCRYPTION_KEY,
            )
        except Exception as exc:
            logger.error("Failed to load inbox messages: %s", exc.__class__.__name__)
            return admin_response("Inbox is unavailable", 503)

        inbox_service.audit_inbox_action(
            user,
            "view_messages",
            metadata={"has_query": bool(query), "result_count": len(messages)},
        )

        return admin_response(
            render_admin_messages_page(
                user,
                messages,
                query=query,
                limit=limit,
                admin_role=inbox_service.INBOX_ADMIN_ROLE,
                csrf_token_builder=inbox_service.inbox_csrf_token,
            )
        )

    @flask_app.route("/admin/messages/<int:message_id>/delete", methods=["POST"])
    def admin_delete_message(message_id: int) -> ResponseReturnValue:
        """Soft-delete one inbox message."""
        user, error_response = inbox_service.require_inbox_user(inbox_service.INBOX_ADMIN_ROLE)
        if error_response:
            return error_response
        if user is None:
            return admin_response("Unauthorized", 401)

        if not inbox_service.valid_inbox_csrf(user["username"], "delete", message_id):
            return admin_response("Forbidden", 403)

        try:
            deleted = inbox_store.soft_delete_message(
                INBOX_DATABASE_URL,
                message_id=message_id,
                deleted_by=user["username"],
            )
        except Exception as exc:
            logger.error("Failed to delete inbox message: %s", exc.__class__.__name__)
            return admin_response("Inbox is unavailable", 503)

        inbox_service.audit_inbox_action(
            user,
            "delete_message",
            target_message_id=message_id,
            metadata={"deleted": deleted},
        )

        return redirect(url_for("admin_messages"), code=303)
