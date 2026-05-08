"""Helpers for reading Meta WhatsApp webhook payloads."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

WebhookObject = dict[str, Any]


def iter_webhook_messages(
    data: WebhookObject,
) -> Iterator[tuple[WebhookObject, WebhookObject]]:
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


def iter_webhook_calls(
    data: WebhookObject,
) -> Iterator[tuple[WebhookObject, WebhookObject]]:
    """Yield every call object from a Meta webhook payload.

    Meta delivers incoming WhatsApp call events under
    ``entry[].changes[].value.calls[]`` with the same envelope shape used
    for messages. The structure mirrors :func:`iter_webhook_messages`.
    """
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

            calls = value.get("calls", [])
            if not isinstance(calls, list):
                continue

            for call in calls:
                if isinstance(call, dict):
                    yield value, call
