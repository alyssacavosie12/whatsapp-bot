"""Admin inbox routes."""

from __future__ import annotations

from flask import Flask

from inbox import admin_panel


def register_admin_routes(flask_app: Flask) -> None:
    """Attach admin inbox endpoints to the Flask app."""
    flask_app.add_url_rule(
        "/admin/messages",
        "admin_messages",
        admin_panel.admin_messages,
        methods=["GET"],
    )
    flask_app.add_url_rule(
        "/admin/messages/<int:message_id>",
        "admin_message_detail",
        admin_panel.admin_message_detail,
        methods=["GET"],
    )
    flask_app.add_url_rule(
        "/admin/messages/<int:message_id>/delete",
        "admin_delete_message",
        admin_panel.admin_delete_message,
        methods=["POST"],
    )
    flask_app.add_url_rule(
        "/admin/data-subject/delete",
        "admin_data_subject_delete",
        admin_panel.admin_data_subject_delete,
        methods=["POST"],
    )
