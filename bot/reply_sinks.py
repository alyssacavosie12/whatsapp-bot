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
    """Outbound message destination for the bot.

    A sink owns both customer-facing replies and internal team notifications
    for one inbound event. If team alerts later move to Slack/email/etc.,
    introduce a separate TeamNotifier and inject it here.
    """

    def send(self, text: str) -> None:
        """Deliver ``text`` to the originating customer."""

    def notify_team(self, message: str) -> None:
        """Send an internal alert to the operations channel."""


@dataclass(frozen=True)
class WhatsAppReplySink:
    """ReplySink that delivers via Meta Cloud API."""

    recipient_id: str

    def send(self, text: str) -> None:
        """Send a customer-facing reply via WhatsApp."""
        whatsapp_client.send_whatsapp_message(self.recipient_id, text)

    def notify_team(self, message: str) -> None:
        """Send an internal team notification via WhatsApp."""
        whatsapp_client.notify_team(message)


@dataclass(frozen=True)
class ChatwootReplySink:
    """ReplySink that delivers customer replies via Chatwoot.

    Internal team alerts intentionally still go through WhatsApp because the
    configured on-call notification phone is a Meta-side operational channel,
    not a Chatwoot inbox concept.
    """

    conversation_id: int | str

    def send(self, text: str) -> None:
        """Send a customer-facing reply via Chatwoot."""
        chatwoot_client.send_message(self.conversation_id, text)

    def notify_team(self, message: str) -> None:
        """Send an internal team notification via WhatsApp, not Chatwoot."""
        whatsapp_client.notify_team(message)
