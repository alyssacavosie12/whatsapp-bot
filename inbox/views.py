"""HTML rendering for the admin inbox."""

from __future__ import annotations

import html
from collections.abc import Callable, Iterable
from pathlib import Path

from inbox.store import InboxMessage

ADMIN_TEMPLATE_PATH = Path(__file__).with_name("admin_panel.html")
ADMIN_MESSAGE_TEMPLATE_PATH = Path(__file__).with_name("admin_message.html")
UNKNOWN_CONTACT_LABEL = "Unknown contact"
LIMIT_OPTIONS = (25, 50, 100, 250, 500)


def _load_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _render_template(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"{{{{{key}}}}}", value)
    return template


def _render_decrypt_controls() -> str:
    """Render browser-only Fernet decrypt controls."""
    return """
        <section class="decrypt-controls" aria-label="Browser-side decrypt controls">
            <label for="fernet-key">Fernet key for local decrypt</label>
            <input id="fernet-key" data-fernet-key type="password"
                autocomplete="off" spellcheck="false"
                placeholder="Paste INBOX_ENCRYPTION_KEY locally">
            <button type="button" data-decrypt-all>Decrypt visible messages</button>
            <button type="button" data-forget-fernet-key>Forget key</button>
            <p class="decrypt-note">
                The key is used only in this browser tab and is not submitted to the server.
            </p>
            <p class="decrypt-status" data-decrypt-status hidden></p>
        </section>
    """


def _render_message_body(message: InboxMessage) -> str:
    """Render message body without server-side plaintext decrypt."""
    if not message.body_encrypted:
        return html.escape(message.body or "")

    token = html.escape(message.body or "", quote=True)
    return f"""
        <div class="encrypted-message" data-fernet-token="{token}">
            <p class="encrypted-placeholder">
                Encrypted message. Decrypt locally in your browser.
            </p>
            <button type="button" data-decrypt-one>Decrypt this message</button>
            <span class="decrypt-result" data-decrypt-result hidden>✓ Decrypted</span>
            <button type="button" data-hide-decrypted hidden>Hide</button>
            <pre class="decrypted-output" data-decrypted-output hidden></pre>
        </div>
    """


def _render_contact_name(sender_name: str) -> str:
    """Render a non-technical contact name fallback."""
    if not sender_name or sender_name == "Encrypted contact":
        return f'<span class="muted-value">{UNKNOWN_CONTACT_LABEL}</span>'

    return html.escape(sender_name)


def _render_limit_options(selected_limit: int) -> str:
    """Render page-size options for the inbox list."""
    options = []
    selected = selected_limit if selected_limit in LIMIT_OPTIONS else 100

    for option in LIMIT_OPTIONS:
        selected_attr = " selected" if option == selected else ""
        options.append(f'<option value="{option}"{selected_attr}>{option}</option>')

    return "\n".join(options)


def _render_copy_value(value: str, *, visible_chars: int = 24) -> str:
    """Render a long identifier as truncated text with a copy button."""
    safe_value = html.escape(value or "n/a")

    if len(value) <= visible_chars:
        visible_value = safe_value
    else:
        keep_start = max(8, visible_chars - 8)
        visible_value = html.escape(f"{value[:keep_start]}...{value[-6:]}")

    return f"""
        <span class="copy-value" title="{safe_value}">
            <span>{visible_value}</span>
            <button type="button" class="copy-button" data-copy-value="{safe_value}">
                Copy
            </button>
        </span>
    """


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
        sender_name = _render_contact_name(message.sender_name)
        sender_phone = html.escape(message.sender_phone_masked or "Hidden")
        message_type = html.escape(message.message_type)
        body = _render_message_body(message)
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
            "limit_options": _render_limit_options(limit),
            "decrypt_controls": _render_decrypt_controls(),
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
    whatsapp_message_id = _render_copy_value(message.whatsapp_message_id or "n/a")
    created_at = html.escape(message.created_at.strftime("%Y-%m-%d %H:%M:%S %Z"))
    sender_name = _render_contact_name(message.sender_name)
    sender_phone = html.escape(message.sender_phone_masked or "Hidden")
    message_type = html.escape(message.message_type)
    body = _render_message_body(message)
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
            "decrypt_controls": _render_decrypt_controls(),
            "body": body,
        },
    )
