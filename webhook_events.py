"""Helpers for reading Meta WhatsApp webhook payloads."""

from __future__ import annotations


def iter_webhook_messages(data: dict):
    """Yield every message object from a Meta webhook payload."""
    entries = data.get("entry", [])
    if not isinstance(entries, list):
        return

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        changes = entry.get("changes", [])
        if not isinstance(changes, list):
            continue

        for change in changes:
            if not isinstance(change, dict):
                continue

            value = change.get("value", {})
            if not isinstance(value, dict):
                continue

            messages = value.get("messages", [])
            if not isinstance(messages, list):
                continue

            for message in messages:
                if isinstance(message, dict):
                    yield value, message
