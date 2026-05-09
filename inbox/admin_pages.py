"""HTML renderers for admin pages outside the message inbox."""

from __future__ import annotations

from flask import render_template

from inbox import service as inbox_service
from inbox import store as inbox_store

__all__ = [
    "format_dt",
    "render_admin_conversation_detail_page",
    "render_admin_conversations_page",
    "render_admin_dashboard_page",
    "render_admin_health_page",
    "render_admin_login_page",
    "render_admin_opt_outs_page",
    "short_hash",
    "valid_hash_id",
]


def short_hash(value: str, *, chars: int = 12) -> str:
    """Return a short display version of a hash."""
    if len(value) <= chars:
        return value

    return f"{value[:chars]}..."


def valid_hash_id(value: str) -> bool:
    """Return True for a safe hash-like URL id."""
    return bool(value and len(value) <= 128 and all(ch.isalnum() for ch in value))


def format_dt(value: object) -> str:
    """Format datetimes for admin templates.

    Jinja auto-escaping is responsible for HTML safety.
    """
    return str(value)


def render_admin_login_page(
    *,
    csrf_token: str,
    error: str = "",
    next_path: str = "",
) -> str:
    """Render a small admin login form."""
    return render_template(
        "admin/login.html",
        csrf_token=csrf_token,
        error=error,
        next_path=next_path,
    )


def render_admin_dashboard_page(
    user: inbox_service.InboxUser,
    stats: inbox_store.InboxDashboardStats,
) -> str:
    """Render the admin dashboard."""
    return render_template(
        "admin/dashboard.html",
        user=user,
        stats=stats,
    )


def render_admin_conversations_page(
    user: inbox_service.InboxUser,
    conversations: list[inbox_store.InboxConversationSummary],
) -> str:
    """Render conversation list."""
    return render_template(
        "admin/conversations.html",
        user=user,
        conversations=conversations,
    )


def render_admin_conversation_detail_page(
    user: inbox_service.InboxUser,
    conversation_id: str,
    messages: list[inbox_store.InboxMessage],
) -> str:
    """Render one conversation."""
    return render_template(
        "admin/conversation_detail.html",
        user=user,
        conversation_id=conversation_id,
        messages=messages,
        short_hash=short_hash,
        format_dt=format_dt,
    )


def render_admin_opt_outs_page(
    user: inbox_service.InboxUser,
    opt_outs: list[inbox_store.InboxOptOutRecord],
) -> str:
    """Render opt-out records."""
    return render_template(
        "admin/opt_outs.html",
        user=user,
        opt_outs=opt_outs,
        short_hash=short_hash,
        format_dt=format_dt,
    )


def render_admin_health_page(
    user: inbox_service.InboxUser,
    components: dict[str, str],
) -> str:
    """Render protected admin health page."""
    return render_template(
        "admin/health.html",
        user=user,
        components=components,
    )
