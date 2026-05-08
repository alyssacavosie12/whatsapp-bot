"""HTML rendering for the admin inbox."""

from __future__ import annotations

import html
from collections.abc import Callable, Iterable
from pathlib import Path

from inbox.store import InboxMessage

ADMIN_TEMPLATE_PATH = Path(__file__).with_name("admin_panel.html")
ADMIN_MESSAGE_TEMPLATE_PATH = Path(__file__).with_name("admin_message.html")


def _load_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _render_template(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"{{{{{key}}}}}", value)
    return template


def render_admin_messages_page(
    user: dict[str, str],
    messages: Iterable[InboxMessage],
    *,
    query: str,
    limit: int,
    admin_role: str,
    csrf_token_builder: Callable[[str, str, int], str],
) -> str:
    """Render the admin inbox as a small self-contained HTML page."""
    safe_query = html.escape(query)
    rows: list[str] = []

    for message in messages:
        created_at = html.escape(message.created_at.strftime("%Y-%m-%d %H:%M:%S %Z"))
        sender_name = html.escape(message.sender_name or "unknown")
        sender_phone = html.escape(message.sender_phone)
        message_type = html.escape(message.message_type)
        body = html.escape(message.body or "")
        encrypted = " yes" if message.body_encrypted else ""
        actions = f'<a class="action" href="/admin/messages/{message.id}">View</a>'

        if user["role"] == admin_role:
            token = csrf_token_builder(user["username"], "delete", message.id)
            actions += f"""
                <form method="post" action="/admin/messages/{message.id}/delete">
                    <input type="hidden" name="csrf_token" value="{token}">
                    <button type="submit">Delete</button>
                </form>
            """

        rows.append(
            f"""
            <tr>
                <td>{created_at}</td>
                <td><strong>{sender_name}</strong><br><span>{sender_phone}</span></td>
                <td>{message_type}{encrypted}</td>
                <td class="body">{body}</td>
                <td class="actions">{actions}</td>
            </tr>
            """
        )

    table_body = "\n".join(rows) or (
        '<tr><td colspan="5" class="empty">No messages found</td></tr>'
    )
    username = html.escape(user["username"])
    role = html.escape(user["role"])

    template = _load_template(ADMIN_TEMPLATE_PATH)
    return _render_template(
        template,
        {
            "page_title": "Messages Inbox",
            "username": username,
            "role": role,
            "safe_query": safe_query,
            "limit": str(limit),
            "table_body": table_body,
        },
    )


def render_admin_message_detail_page(
    user: dict[str, str],
    message: InboxMessage,
    *,
    admin_role: str,
    csrf_token_builder: Callable[[str, str, int], str],
) -> str:
    """Render a single-message detail view for the admin inbox."""
    username = html.escape(user["username"])
    role = html.escape(user["role"])
    message_id = str(message.id)
    whatsapp_message_id = html.escape(message.whatsapp_message_id or "n/a")
    created_at = html.escape(message.created_at.strftime("%Y-%m-%d %H:%M:%S %Z"))
    sender_name = html.escape(message.sender_name or "unknown")
    sender_phone = html.escape(message.sender_phone)
    message_type = html.escape(message.message_type)
    body = html.escape(message.body or "")
    body_encrypted = "yes" if message.body_encrypted else "no"
    body_length = str(message.body_length)
    deleted_at = (
        html.escape(message.deleted_at.strftime("%Y-%m-%d %H:%M:%S %Z"))
        if message.deleted_at
        else "No"
    )
    deleted_by = html.escape(message.deleted_by or "-") if message.deleted_at else "-"

    delete_action = ""
    if user["role"] == admin_role and message.deleted_at is None:
        token = csrf_token_builder(user["username"], "delete", message.id)
        delete_action = f"""
            <form method="post" action="/admin/messages/{message.id}/delete">
                <input type="hidden" name="csrf_token" value="{token}">
                <button type="submit">Delete message</button>
            </form>
        """

    template = _load_template(ADMIN_MESSAGE_TEMPLATE_PATH)
    return _render_template(
        template,
        {
            "page_title": f"Message {message_id}",
            "username": username,
            "role": role,
            "back_url": "/admin/messages",
            "message_id": message_id,
            "whatsapp_message_id": whatsapp_message_id,
            "created_at": created_at,
            "sender_name": sender_name,
            "sender_phone": sender_phone,
            "message_type": message_type,
            "body_encrypted": body_encrypted,
            "body_length": body_length,
            "deleted_at": deleted_at,
            "deleted_by": deleted_by,
            "delete_action": delete_action,
            "body": body,
        },
    )
