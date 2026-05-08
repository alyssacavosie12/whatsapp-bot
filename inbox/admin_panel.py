"""Compatibility facade for admin inbox request handlers."""

from __future__ import annotations

from inbox.admin_arco import admin_data_subject_delete
from inbox.admin_auth import admin_login, admin_logout
from inbox.admin_conversations import admin_conversation_detail, admin_conversations
from inbox.admin_dashboard import admin_index
from inbox.admin_health import admin_health
from inbox.admin_messages import (
    admin_delete_message,
    admin_message_detail,
    admin_messages,
)
from inbox.admin_opt_outs import admin_opt_outs

__all__ = [
    "admin_conversation_detail",
    "admin_conversations",
    "admin_data_subject_delete",
    "admin_delete_message",
    "admin_health",
    "admin_index",
    "admin_login",
    "admin_logout",
    "admin_message_detail",
    "admin_messages",
    "admin_opt_outs",
]
