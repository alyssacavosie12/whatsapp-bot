"""Shared data models for inbound message processing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from core.sender_id import SenderId

TEXT_MESSAGE_TYPE: Final = "text"

MessageType = Literal[
    "text",
    "image",
    "document",
    "audio",
    "video",
    "non_text",
    "text_sensitive_redacted",
]

ResponseStatus = Literal[
    "ok",
    "duplicate",
    "invalid sender",
    "invalid caller",
    "invalid event",
    "opted out",
    "opt out recorded",
    "rate limited",
]

__all__ = [
    "InboxStorageResult",
    "IncomingMessage",
    "MessageType",
    "ResponsePlan",
    "ResponseStatus",
    "TEXT_MESSAGE_TYPE",
]


@dataclass(frozen=True, kw_only=True)
class IncomingMessage:
    """Normalized inbound WhatsApp or Chatwoot message."""

    message_id: str
    sender: SenderId
    masked_sender: str
    sender_name: str
    message_type: MessageType | str
    text: str

    @property
    def sender_id(self) -> str:
        """Return the canonical sender id used for storage and replies."""
        return self.sender.value

    @property
    def is_text(self) -> bool:
        """Return True when this is a text message."""
        return self.message_type == TEXT_MESSAGE_TYPE


@dataclass(frozen=True, kw_only=True)
class InboxStorageResult:
    """Result of preparing and queuing inbox persistence."""

    is_first_contact: bool
    sensitive_category: str | None


@dataclass(frozen=True, kw_only=True)
class ResponsePlan:
    """Outbound actions produced by response routing."""

    reply_text: str | None = None
    team_notification: str | None = None
    status: ResponseStatus = "ok"
