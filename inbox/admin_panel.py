"""Admin inbox request handlers."""

from __future__ import annotations

import html
import logging

from flask import jsonify, redirect, request, url_for
from flask.typing import ResponseReturnValue

from core.phone_utils import mask_phone
from core.sender_id import parse_sender_id
from inbox import service as inbox_service
from inbox import store as inbox_store
from inbox.security import admin_response
from inbox.views import render_admin_message_detail_page, render_admin_messages_page
from settings import INBOX_DATABASE_URL, INBOX_ENCRYPTION_KEY

logger = logging.getLogger(__name__)


def _safe_next_path(raw_next: str) -> str:
    """Allow only local redirect targets after login."""
    if raw_next.startswith("/") and not raw_next.startswith("//"):
        return raw_next

    return url_for("admin.admin_messages")


def _render_admin_login_page(*, error: str = "", next_path: str = "") -> str:
    """Render a small admin login form."""
    csrf_token = html.escape(inbox_service.inbox_login_csrf_token())
    safe_error = html.escape(error)
    safe_next = html.escape(next_path or url_for("admin.admin_messages"))

    error_html = f'<p class="error">{safe_error}</p>' if safe_error else ""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Tulum Botox Admin Login</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #faf7f2;
      color: #1f2933;
      margin: 0;
      padding: 40px 16px;
    }}
    main {{
      max-width: 420px;
      margin: 0 auto;
      background: #fff;
      border: 1px solid #e5e0d8;
      border-radius: 16px;
      padding: 28px;
      box-shadow: 0 10px 30px rgba(0,0,0,.06);
    }}
    h1 {{
      margin: 0 0 18px;
      font-size: 24px;
    }}
    label {{
      display: block;
      margin-top: 14px;
      font-weight: 600;
    }}
    input {{
      width: 100%;
      box-sizing: border-box;
      margin-top: 6px;
      padding: 10px 12px;
      border: 1px solid #cfd6dd;
      border-radius: 10px;
      font: inherit;
    }}
    button {{
      width: 100%;
      margin-top: 20px;
      padding: 11px 14px;
      border: 0;
      border-radius: 10px;
      background: #111827;
      color: white;
      font-weight: 700;
      cursor: pointer;
    }}
    .error {{
      background: #fee2e2;
      border: 1px solid #fecaca;
      color: #991b1b;
      padding: 10px 12px;
      border-radius: 10px;
    }}
    .hint {{
      color: #667085;
      font-size: 14px;
      margin-top: 16px;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Tulum Botox Admin</h1>
    {error_html}
    <form method="post" action="{url_for("admin.admin_login")}">
      <input type="hidden" name="csrf_token" value="{csrf_token}">
      <input type="hidden" name="next" value="{safe_next}">

      <label for="username">Username</label>
      <input id="username" name="username" autocomplete="username" required>

      <label for="password">Password</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required>

      <button type="submit">Log in</button>
    </form>
    <p class="hint">Session expires after inactivity.</p>
  </main>
</body>
</html>"""


def _render_admin_dashboard_page(
    user: inbox_service.InboxUser,
    stats: inbox_store.InboxDashboardStats,
) -> str:
    """Render the admin dashboard."""
    safe_username = html.escape(user["username"])
    safe_role = html.escape(user["role"])

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Tulum Botox Admin Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #faf7f2;
      color: #1f2933;
      margin: 0;
      padding: 24px;
    }}
    main {{
      max-width: 1100px;
      margin: 0 auto;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      margin-bottom: 24px;
    }}
    h1 {{
      margin: 0;
      font-size: 28px;
    }}
    .muted {{
      color: #667085;
      font-size: 14px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin: 24px 0;
    }}
    .card {{
      background: #fff;
      border: 1px solid #e5e0d8;
      border-radius: 16px;
      padding: 18px;
      box-shadow: 0 8px 24px rgba(0,0,0,.05);
    }}
    .number {{
      font-size: 32px;
      font-weight: 800;
      margin: 8px 0 0;
    }}
    .label {{
      color: #667085;
      font-size: 14px;
      font-weight: 600;
    }}
    nav {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 24px;
    }}
    a, button {{
      display: inline-block;
      padding: 10px 14px;
      border-radius: 10px;
      border: 1px solid #d0d5dd;
      background: #fff;
      color: #111827;
      text-decoration: none;
      font: inherit;
      cursor: pointer;
    }}
    .primary {{
      background: #111827;
      color: #fff;
      border-color: #111827;
    }}
    form {{
      margin: 0;
    }}
    .note {{
      background: #fff7ed;
      border: 1px solid #fed7aa;
      color: #9a3412;
      border-radius: 12px;
      padding: 12px 14px;
      margin-top: 18px;
      font-size: 14px;
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Tulum Botox Admin</h1>
        <div class="muted">Signed in as {safe_username} · {safe_role}</div>
      </div>
      <form method="post" action="{url_for("admin.admin_logout")}">
        <button type="submit">Log out</button>
      </form>
    </header>

    <section class="grid" aria-label="Dashboard counters">
      <div class="card">
        <div class="label">Messages today</div>
        <div class="number">{stats.messages_today}</div>
      </div>
      <div class="card">
        <div class="label">Total messages</div>
        <div class="number">{stats.messages_total}</div>
      </div>
      <div class="card">
        <div class="label">Active messages</div>
        <div class="number">{stats.messages_active}</div>
      </div>
      <div class="card">
        <div class="label">Deleted messages</div>
        <div class="number">{stats.messages_deleted}</div>
      </div>
      <div class="card">
        <div class="label">Opt-in proofs</div>
        <div class="number">{stats.opt_in_proofs_total}</div>
      </div>
      <div class="card">
        <div class="label">Opt-outs</div>
        <div class="number">{stats.opt_outs_total}</div>
      </div>
    </section>

    <nav>
      <a class="primary" href="{url_for("admin.admin_messages")}">Open messages</a>
      <a href="{url_for("admin.admin_login")}">Login page</a>
      <a href="/health">System health</a>
    </nav>

    <p class="note">
      FAQ hits and AI calls are not shown yet because they are not currently stored
      as metrics. Add a telemetry table to track those accurately.
    </p>
  </main>
</body>
</html>"""


def admin_index() -> ResponseReturnValue:
    """Show the admin dashboard."""
    user, error_response = inbox_service.require_inbox_user(inbox_service.INBOX_VIEWER_ROLE)
    if error_response:
        return error_response
    if user is None:
        return admin_response("Unauthorized", 401)

    try:
        stats = inbox_store.get_dashboard_stats(INBOX_DATABASE_URL)
    except Exception:
        logger.exception("Failed to load admin dashboard stats")
        return admin_response("Dashboard is unavailable", 503)

    inbox_service.audit_inbox_action(user, "view_dashboard")

    return admin_response(_render_admin_dashboard_page(user, stats))


def admin_login() -> ResponseReturnValue:
    """Show and process the admin login form."""
    next_path = _safe_next_path(request.values.get("next", ""))

    if request.method == "GET":
        if inbox_service.current_inbox_user():
            return redirect(next_path, code=303)

        return admin_response(_render_admin_login_page(next_path=next_path))

    if not inbox_service.valid_inbox_login_csrf():
        return admin_response(
            _render_admin_login_page(
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
            _render_admin_login_page(
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
            INBOX_DATABASE_URL,
            query=query,
            limit=limit,
            encryption_key=INBOX_ENCRYPTION_KEY,
        )
    except Exception:
        logger.exception("Failed to load inbox messages")
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
            INBOX_DATABASE_URL,
            message_id,
            encryption_key=INBOX_ENCRYPTION_KEY,
        )
    except Exception:
        logger.exception("Failed to load inbox message")
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
            INBOX_DATABASE_URL,
            message_id=message_id,
            deleted_by=user["username"],
        )
    except Exception:
        logger.exception("Failed to delete inbox message")
        return admin_response("Inbox is unavailable", 503)

    inbox_service.audit_inbox_action(
        user,
        "delete_message",
        target_message_id=message_id,
        metadata={"deleted": deleted},
    )

    return redirect(url_for("admin.admin_messages"), code=303)


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
        logger.exception(
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
