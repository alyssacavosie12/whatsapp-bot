"""Admin authentication route handlers."""

from __future__ import annotations

from flask import redirect, request, url_for
from flask.typing import ResponseReturnValue

from inbox import service as inbox_service
from inbox.admin_pages import render_admin_login_page
from inbox.security import admin_response


def _safe_next_path(raw_next: str) -> str:
    """Allow only local redirect targets after login."""
    if raw_next.startswith("/") and not raw_next.startswith("//"):
        return raw_next

    return url_for("admin.admin_messages")


def admin_login() -> ResponseReturnValue:
    """Show and process the admin login form."""
    next_path = _safe_next_path(request.values.get("next", ""))

    if request.method == "GET":
        if inbox_service.current_inbox_user():
            return redirect(next_path, code=303)

        return admin_response(
            render_admin_login_page(
                csrf_token=inbox_service.inbox_login_csrf_token(),
                next_path=next_path,
            )
        )

    if not inbox_service.valid_inbox_login_csrf():
        return admin_response(
            render_admin_login_page(
                csrf_token=inbox_service.inbox_login_csrf_token(),
                error="Login form expired. Please try again.",
                next_path=next_path,
            ),
            400,
        )

    username = request.form.get("username", "")
    password = request.form.get("password", "")

    user, error_response = inbox_service.login_inbox_user(username, password)
    if error_response:
        return error_response

    if user is None:
        return admin_response(
            render_admin_login_page(
                csrf_token=inbox_service.inbox_login_csrf_token(),
                error="Invalid username or password.",
                next_path=next_path,
            ),
            401,
        )

    inbox_service.audit_inbox_action(user, "login_success")
    return redirect(next_path, code=303)


def admin_logout() -> ResponseReturnValue:
    """End the current admin session."""
    user = inbox_service.current_inbox_user()
    if user:
        inbox_service.audit_inbox_action(user, "logout")

    inbox_service.clear_inbox_session()
    return redirect(url_for("admin.admin_login"), code=303)
