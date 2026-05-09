"""Admin opt-out route handler."""

from __future__ import annotations

import logging

from flask.typing import ResponseReturnValue

from inbox import service as inbox_service
from inbox import store as inbox_store
from inbox.admin_pages import render_admin_opt_outs_page
from inbox.security import admin_response
from inbox.store_common import STORE_OPERATION_ERRORS

logger = logging.getLogger(__name__)


def admin_opt_outs() -> ResponseReturnValue:
    """Show opt-out records."""
    user, error_response = inbox_service.require_inbox_user(inbox_service.INBOX_VIEWER_ROLE)
    if error_response:
        return error_response
    if user is None:
        return admin_response("Unauthorized", 401)

    try:
        opt_outs = inbox_store.list_opt_out_records(inbox_service.inbox_database_url())
    except STORE_OPERATION_ERRORS:
        logger.exception("Failed to load opt-out records")
        return admin_response("Opt-outs are unavailable", 503)

    inbox_service.audit_inbox_action(
        user,
        "view_opt_outs",
        metadata={"result_count": len(opt_outs)},
    )

    return admin_response(render_admin_opt_outs_page(user, opt_outs))
