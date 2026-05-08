"""Protected admin health route handler."""

from __future__ import annotations

from flask.typing import ResponseReturnValue

from bot.ai_responder import anthropic_circuit_status
from core.cache import get_redis
from core.database import get_db_pool
from inbox import service as inbox_service
from inbox.admin_pages import render_admin_health_page
from inbox.security import admin_response
from settings import REDIS_URL


def admin_health_components() -> dict[str, str]:
    """Return protected admin health components."""
    components: dict[str, str] = {
        "anthropic": anthropic_circuit_status(),
        "postgres": "disabled",
        "redis": "disabled",
    }

    if REDIS_URL:
        try:
            get_redis(REDIS_URL).ping()
            components["redis"] = "ok"
        except Exception:
            components["redis"] = "degraded"

    database_url = inbox_service.inbox_database_url()
    if inbox_service.inbox_enabled() and database_url:
        try:
            with get_db_pool(database_url).connection() as conn:
                conn.execute("SELECT 1")
            components["postgres"] = "ok"
        except Exception:
            components["postgres"] = "degraded"

    return components


def admin_health() -> ResponseReturnValue:
    """Show protected admin health status."""
    user, error_response = inbox_service.require_inbox_user(inbox_service.INBOX_VIEWER_ROLE)
    if error_response:
        return error_response
    if user is None:
        return admin_response("Unauthorized", 401)

    components = admin_health_components()
    inbox_service.audit_inbox_action(user, "view_admin_health")

    return admin_response(render_admin_health_page(user, components))
