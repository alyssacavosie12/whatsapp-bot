"""Admin dashboard route handler."""

from __future__ import annotations

import logging

from flask.typing import ResponseReturnValue

from inbox import service as inbox_service
from inbox import store as inbox_store
from inbox.admin_pages import render_admin_dashboard_page
from inbox.security import admin_response

logger = logging.getLogger(__name__)


def admin_index() -> ResponseReturnValue:
    """Show the admin dashboard."""
    user, error_response = inbox_service.require_inbox_user(inbox_service.INBOX_VIEWER_ROLE)
    if error_response:
        return error_response
    if user is None:
        return admin_response("Unauthorized", 401)

    try:
        stats = inbox_store.get_dashboard_stats(inbox_service.inbox_database_url())
    except Exception:
        logger.exception("Failed to load admin dashboard stats")
        return admin_response("Dashboard is unavailable", 503)

    inbox_service.audit_inbox_action(user, "view_dashboard")

    return admin_response(render_admin_dashboard_page(user, stats))
