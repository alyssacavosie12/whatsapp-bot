"""Admin ARCO data-subject request handlers."""

from __future__ import annotations

import logging

from flask import jsonify, request
from flask.typing import ResponseReturnValue

from core.sender_id import mask_sender_id, parse_sender_id
from inbox import service as inbox_service
from inbox.security import admin_response
from inbox.store_common import STORE_OPERATION_ERRORS

logger = logging.getLogger(__name__)


def _delete_opt_out_requested() -> bool:
    """Return True when the admin requested opt-out record deletion too."""
    return request.form.get("delete_opt_out_record", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _data_subject_identifier() -> str:
    """Return the submitted phone or external id value."""
    return (
        request.form.get("phone", "").strip()
        or request.form.get(
            "external_id",
            "",
        ).strip()
    )


def admin_data_subject_delete() -> ResponseReturnValue:
    """Hard-delete all stored data for one user (LFPDPPP/CCPA ARCO Cancelacion)."""
    user, error_response = inbox_service.require_inbox_user(inbox_service.INBOX_ADMIN_ROLE)
    if error_response:
        return error_response
    if user is None:
        return admin_response("Unauthorized", 401)

    if not inbox_service.valid_inbox_csrf(user["username"], "arco_delete", 0):
        return admin_response("Forbidden", 403)

    sender = parse_sender_id(_data_subject_identifier())
    if sender is None:
        return admin_response(
            "phone or external_id is required and must be a valid E.164 or BSUID",
            400,
        )

    delete_opt_out = _delete_opt_out_requested()

    try:
        counts = inbox_service.delete_user_data(
            sender.value,
            delete_opt_out_record=delete_opt_out,
        )
    except STORE_OPERATION_ERRORS as exc:
        logger.exception(
            "arco_delete_failed sender=%s error=%s",
            mask_sender_id(sender),
            exc.__class__.__name__,
        )
        return admin_response("Inbox is unavailable", 503)

    inbox_service.audit_inbox_action(
        user,
        "arco_cancelacion",
        metadata={
            "sender_id_type": sender.id_type,
            "sender_masked": mask_sender_id(sender),
            "delete_opt_out_record": delete_opt_out,
            "counts": counts,
        },
    )

    response = jsonify({"status": "ok", "deleted": counts})
    response.headers["Cache-Control"] = "no-store"
    return response, 200
