"""HTML rendering for the admin inbox."""

from __future__ import annotations

import html
from collections.abc import Callable, Iterable

from inbox.store import InboxMessage


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
        delete_cell = ""

        if user["role"] == admin_role:
            token = csrf_token_builder(user["username"], "delete", message.id)
            delete_cell = f"""
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
                <td>{delete_cell}</td>
            </tr>
            """
        )

    table_body = "\n".join(rows) or (
        '<tr><td colspan="5" class="empty">No messages found</td></tr>'
    )
    username = html.escape(user["username"])
    role = html.escape(user["role"])

    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Messages Inbox</title>
    <style>
        :root {{
            color-scheme: light;
            font-family: Arial, sans-serif;
            background: #f6f7f9;
            color: #18212f;
        }}
        body {{
            margin: 0;
            padding: 24px;
        }}
        main {{
            max-width: 1180px;
            margin: 0 auto;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            gap: 16px;
            align-items: center;
            margin-bottom: 20px;
        }}
        h1 {{
            font-size: 28px;
            margin: 0;
        }}
        .meta {{
            color: #536071;
            font-size: 14px;
        }}
        form.search {{
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
        }}
        input[type="search"], input[type="number"] {{
            border: 1px solid #c9d0da;
            border-radius: 6px;
            font: inherit;
            padding: 9px 10px;
        }}
        input[type="search"] {{
            min-width: 260px;
            flex: 1;
        }}
        input[type="number"] {{
            width: 96px;
        }}
        button {{
            border: 1px solid #27364a;
            border-radius: 6px;
            background: #27364a;
            color: white;
            cursor: pointer;
            font: inherit;
            padding: 9px 12px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border: 1px solid #d9dee7;
        }}
        th, td {{
            border-bottom: 1px solid #e3e7ee;
            padding: 12px;
            text-align: left;
            vertical-align: top;
            font-size: 14px;
        }}
        th {{
            background: #eef2f6;
            color: #27364a;
        }}
        td.body {{
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            max-width: 520px;
        }}
        td span, .empty {{
            color: #647184;
        }}
        @media (max-width: 760px) {{
            body {{
                padding: 12px;
            }}
            header, form.search {{
                display: block;
            }}
            input[type="search"], input[type="number"], button {{
                box-sizing: border-box;
                margin-top: 8px;
                width: 100%;
            }}
            table, thead, tbody, th, td, tr {{
                display: block;
            }}
            thead {{
                display: none;
            }}
            tr {{
                border-bottom: 1px solid #d9dee7;
            }}
            td {{
                border-bottom: 0;
            }}
        }}
    </style>
</head>
<body>
    <main>
        <header>
            <h1>Messages Inbox</h1>
            <div class="meta">{username} ({role})</div>
        </header>
        <form class="search" method="get" action="/admin/messages">
            <input type="search" name="q" value="{safe_query}"
                placeholder="Search name, phone, text">
            <input type="number" name="limit" value="{limit}" min="1" max="500">
            <button type="submit">Search</button>
        </form>
        <table>
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Contact</th>
                    <th>Type</th>
                    <th>Message</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>{table_body}</tbody>
        </table>
    </main>
</body>
</html>"""
