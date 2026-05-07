"""Strict-enough validation for Meta WhatsApp webhook payloads."""

from __future__ import annotations

from typing import Any


WEBHOOK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["entry"],
    "additionalProperties": True,
    "properties": {
        "entry": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["changes"],
                "additionalProperties": True,
                "properties": {
                    "changes": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["value"],
                            "additionalProperties": True,
                            "properties": {
                                "value": {
                                    "type": "object",
                                    "additionalProperties": True,
                                    "properties": {
                                        "contacts": {"type": "array"},
                                        "messages": {"type": "array"},
                                        "statuses": {"type": "array"},
                                    },
                                }
                            },
                        },
                    }
                },
            },
        }
    },
}


def validate_webhook_payload(data: Any) -> tuple[bool, str]:
    """Validate the envelope before the app reads nested webhook fields."""
    try:
        from jsonschema import ValidationError, validate
    except ImportError:
        return _manual_validate_webhook_payload(data)

    try:
        validate(instance=data, schema=WEBHOOK_SCHEMA)
    except ValidationError as exc:
        return False, exc.message

    return _manual_validate_webhook_payload(data)


def _manual_validate_webhook_payload(data: Any) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "payload must be an object"

    entries = data.get("entry")
    if not isinstance(entries, list) or not entries:
        return False, "entry must be a non-empty array"

    for entry in entries:
        if not isinstance(entry, dict):
            return False, "entry items must be objects"

        changes = entry.get("changes")
        if not isinstance(changes, list) or not changes:
            return False, "changes must be a non-empty array"

        for change in changes:
            if not isinstance(change, dict):
                return False, "change items must be objects"

            value = change.get("value")
            if not isinstance(value, dict):
                return False, "change.value must be an object"

            messages = value.get("messages", [])
            if not isinstance(messages, list):
                return False, "messages must be an array"

            for message in messages:
                if not isinstance(message, dict):
                    return False, "message items must be objects"

                if "from" in message and not isinstance(message["from"], str):
                    return False, "message.from must be a string"

                if "type" in message and not isinstance(message["type"], str):
                    return False, "message.type must be a string"

                if message.get("type") == "text" and not isinstance(
                    message.get("text", {}),
                    dict,
                ):
                    return False, "text message payload must be an object"

    return True, ""
