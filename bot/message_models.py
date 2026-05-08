"""Shared data models for inbound message processing."""

from __future__ import annotations

from dataclasses import dataclass

from core.sender_id import SenderId


@dataclass(frozen=True)
class IncomingMessage:
    """Normalized inbound WhatsApp message."""

    message_id: str
    sender: SenderId
    masked_sender: str
    sender_name: str
    message_type: str
    text: str

    @property
    def sender_id(self) -> str:
        """Return the canonical sender id used for storage and replies."""
        return self.sender.value

    @property
    def is_text(self) -> bool:
        """Return True when this is a text message."""
        return self.message_type == "text"


@dataclass(frozen=True)
class InboxStorageResult:
    """Result of preparing and queuing inbox persistence."""

    is_first_contact: bool
    sensitive_category: str | None


@dataclass(frozen=True)
class ResponsePlan:
    """Outbound actions produced by response routing."""

    reply_text: str | None = None
    team_notification: str | None = None
    status: str = "ok"
