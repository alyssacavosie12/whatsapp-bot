"""Outbound reply destinations for supported transports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from bot import chatwoot_client, whatsapp_client

__all__ = [
    "ChatwootReplySink",
    "ReplySink",
    "WhatsAppReplySink",
]


class ReplySink(Protocol):
    """Outbound message destination for the bot."""

    def send(self, text: str) -> None:
        """Deliver ``text`` to the originating customer."""

    def notify_team(self, message: str) -> None:
        """Send an internal alert to the operations channel."""


@dataclass(frozen=True)
class WhatsAppReplySink:
    """ReplySink that delivers via Meta Cloud API."""

    recipient_id: str

    def send(self, text: str) -> None:
        whatsapp_client.send_whatsapp_message(self.recipient_id, text)

    def notify_team(self, message: str) -> None:
        whatsapp_client.notify_team(message)


@dataclass(frozen=True)
class ChatwootReplySink:
    """ReplySink that delivers via Chatwoot's agent-bot REST API.

    Team notifications continue to flow through ``whatsapp_client`` because
    the on-call operator notification phone is a Meta-side concept.
    """

    conversation_id: int | str

    def send(self, text: str) -> None:
        chatwoot_client.send_message(self.conversation_id, text)

    def notify_team(self, message: str) -> None:
        whatsapp_client.notify_team(message)