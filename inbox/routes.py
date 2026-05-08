"""Admin inbox blueprint routes."""

from __future__ import annotations

from flask import Blueprint, Flask

from inbox import (
    admin_arco,
    admin_auth,
    admin_conversations,
    admin_dashboard,
    admin_health,
    admin_messages,
    admin_opt_outs,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

admin_bp.add_url_rule(
    "/",
    "admin_index",
    admin_dashboard.admin_index,
    methods=["GET"],
)
admin_bp.add_url_rule(
    "/login",
    "admin_login",
    admin_auth.admin_login,
    methods=["GET", "POST"],
)
admin_bp.add_url_rule(
    "/logout",
    "admin_logout",
    admin_auth.admin_logout,
    methods=["GET", "POST"],
)
admin_bp.add_url_rule(
    "/messages",
    "admin_messages",
    admin_messages.admin_messages,
    methods=["GET"],
)
admin_bp.add_url_rule(
    "/messages/<int:message_id>",
    "admin_message_detail",
    admin_messages.admin_message_detail,
    methods=["GET"],
)
admin_bp.add_url_rule(
    "/messages/<int:message_id>/delete",
    "admin_delete_message",
    admin_messages.admin_delete_message,
    methods=["POST"],
)
admin_bp.add_url_rule(
    "/conversations",
    "admin_conversations",
    admin_conversations.admin_conversations,
    methods=["GET"],
)
admin_bp.add_url_rule(
    "/conversations/<conversation_id>",
    "admin_conversation_detail",
    admin_conversations.admin_conversation_detail,
    methods=["GET"],
)
admin_bp.add_url_rule(
    "/opt-outs",
    "admin_opt_outs",
    admin_opt_outs.admin_opt_outs,
    methods=["GET"],
)
admin_bp.add_url_rule(
    "/health",
    "admin_health",
    admin_health.admin_health,
    methods=["GET"],
)
admin_bp.add_url_rule(
    "/data-subject/delete",
    "admin_data_subject_delete",
    admin_arco.admin_data_subject_delete,
    methods=["POST"],
)


def register_admin_routes(flask_app: Flask) -> None:
    """Attach admin inbox blueprint to the Flask app."""
    flask_app.register_blueprint(admin_bp)
