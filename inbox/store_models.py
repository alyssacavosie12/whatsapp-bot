"""Data models returned by the inbox store."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class InboxMessage:
    """One sanitized admin inbox message row."""

    id: int
    whatsapp_message_id: str
    direction: str
    sender_phone: str
    sender_phone_masked: str
    sender_name: str
    message_type: str
    body: str
    body_encrypted: bool
    body_length: int
    created_at: datetime
    deleted_at: datetime | None
    deleted_by: str


@dataclass(frozen=True)
class InboxConversationSummary:
    """One conversation summary grouped by sender hash."""

    conversation_id: str
    sender_phone_masked: str
    sender_name: str
    last_message_type: str
    last_body: str
    last_body_encrypted: bool
    message_count: int
    last_message_at: datetime


@dataclass(frozen=True)
class InboxOptOutRecord:
    """One opt-out record for the admin UI."""

    id: int
    sender_external_id_hash: str
    sender_external_id_type: str
    source: str
    keyword_used: str
    language: str
    recorded_at: datetime


@dataclass(frozen=True)
class InboxDashboardStats:
    """Aggregate counters for the admin dashboard."""

    messages_total: int
    messages_today: int
    messages_active: int
    messages_deleted: int
    opt_in_proofs_total: int
    opt_outs_total: int
