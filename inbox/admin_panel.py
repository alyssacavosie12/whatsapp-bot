"""Admin inbox request handlers."""

from __future__ import annotations

import logging

from flask import jsonify, redirect, request, url_for
from flask.typing import ResponseReturnValue

from core.phone_utils import mask_phone
from core.sender_id import parse_sender_id
from inbox import service as inbox_service
from inbox import store as inbox_store
from inbox.security import admin_response
from inbox.views import render_admin_message_detail_page, render_admin_messages_page

logger = logging.getLogger(__name__)


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
            inbox_service.INBOX_DATABASE_URL,
            query=query,
            limit=limit,
            encryption_key=inbox_service.INBOX_ENCRYPTION_KEY,
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


def admin_message_detail(message_id: int) -> ResponseReturnValue:
    """Show a single inbox message for review."""
    user, error_response = inbox_service.require_inbox_user(inbox_service.INBOX_VIEWER_ROLE)
    if error_response:
        return error_response
    if user is None:
        return admin_response("Unauthorized", 401)

    try:
        message = inbox_store.get_message_by_id(
            inbox_service.INBOX_DATABASE_URL,
            message_id,
            encryption_key=inbox_service.INBOX_ENCRYPTION_KEY,
        )
    except Exception as exc:
        logger.error("Failed to load inbox message: %s", exc.__class__.__name__)
        return admin_response("Inbox is unavailable", 503)

    if message is None:
        return admin_response("Message not found", 404)

    inbox_service.audit_inbox_action(
        user,
        "view_message",
        target_message_id=message_id,
    )

    return admin_response(
        render_admin_message_detail_page(
            user,
            message,
            admin_role=inbox_service.INBOX_ADMIN_ROLE,
            csrf_token_builder=inbox_service.inbox_csrf_token,
        )
    )


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
            inbox_service.INBOX_DATABASE_URL,
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


def admin_data_subject_delete() -> ResponseReturnValue:
    """Hard-delete all stored data for one user (LFPDPPP/CCPA ARCO Cancelacion)."""
    user, error_response = inbox_service.require_inbox_user(inbox_service.INBOX_ADMIN_ROLE)
    if error_response:
        return error_response
    if user is None:
        return admin_response("Unauthorized", 401)

    if not inbox_service.valid_inbox_csrf(user["username"], "arco_delete", 0):
        return admin_response("Forbidden", 403)

    raw_id = request.form.get("phone", "").strip() or request.form.get("external_id", "").strip()
    sender = parse_sender_id(raw_id)
    if sender is None:
        return admin_response(
            "phone or external_id is required and must be a valid E.164 or BSUID",
            400,
        )

    delete_opt_out = request.form.get("delete_opt_out_record", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    try:
        counts = inbox_service.delete_user_data(
            sender.value,
            delete_opt_out_record=delete_opt_out,
        )
    except Exception as exc:
        logger.error(
            "arco_delete_failed sender=%s error=%s",
            mask_phone(sender.value),
            exc.__class__.__name__,
        )
        return admin_response("Inbox is unavailable", 503)

    inbox_service.audit_inbox_action(
        user,
        "arco_cancelacion",
        metadata={
            "sender_id_type": sender.id_type,
            "sender_masked": mask_phone(sender.value),
            "delete_opt_out_record": delete_opt_out,
            "counts": counts,
        },
    )

    response = jsonify({"status": "ok", "deleted": counts})
    response.headers["Cache-Control"] = "no-store"
    return response, 200
