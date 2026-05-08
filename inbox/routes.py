"""Admin inbox blueprint routes."""

from __future__ import annotations

from flask import Blueprint, Flask

from inbox import admin_panel

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

admin_bp.add_url_rule(
    "/messages",
    "admin_messages",
    admin_panel.admin_messages,
    methods=["GET"],
)
admin_bp.add_url_rule(
    "/messages/<int:message_id>",
    "admin_message_detail",
    admin_panel.admin_message_detail,
    methods=["GET"],
)
admin_bp.add_url_rule(
    "/messages/<int:message_id>/delete",
    "admin_delete_message",
    admin_panel.admin_delete_message,
    methods=["POST"],
)
admin_bp.add_url_rule(
    "/data-subject/delete",
    "admin_data_subject_delete",
    admin_panel.admin_data_subject_delete,
    methods=["POST"],
)


def register_admin_routes(flask_app: Flask) -> None:
    """Attach admin inbox blueprint to the Flask app."""
    flask_app.register_blueprint(admin_bp)
