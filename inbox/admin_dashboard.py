"""Admin dashboard route handler."""

from __future__ import annotations

import logging

from flask.typing import ResponseReturnValue

from inbox import service as inbox_service
from inbox import store as inbox_store
from inbox.admin_pages import render_admin_dashboard_page
from inbox.security import admin_response
from inbox.store_common import STORE_OPERATION_ERRORS

logger = logging.getLogger(__name__)

__all__ = ["admin_index"]


def admin_index() -> ResponseReturnValue:
    """Show the admin dashboard.

    This route intentionally stays thin: expensive aggregation, caching, or
    precomputed counters should live in ``inbox.store.get_dashboard_stats`` or
    a dedicated stats service rather than in the Flask handler.
    """
    user, error_response = inbox_service.require_inbox_user(inbox_service.INBOX_VIEWER_ROLE)
    if error_response:
        return error_response
    if user is None:
        return admin_response("Unauthorized", 401)

    try:
        stats = inbox_store.get_dashboard_stats(inbox_service.inbox_database_url())
    except STORE_OPERATION_ERRORS:
        logger.exception("Failed to load admin dashboard stats")
        return admin_response("Dashboard is unavailable", 503)

    inbox_service.audit_inbox_action(user, "view_dashboard")

    return admin_response(render_admin_dashboard_page(user, stats))
