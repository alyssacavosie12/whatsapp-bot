"""Webhook route for Chatwoot agent_bot deliveries.

Chatwoot sends a webhook to the URL configured on the agent bot whenever a
new message arrives in any inbox the bot is assigned to. We process only
``message_created`` events for ``incoming`` (customer -> bot) text messages
and dispatch them to :func:`bot.message_processor.process_chatwoot_message`.

Outbound and private (internal note) messages are ignored — those are echoes
of the bot's own replies or human-agent activity, not new customer input.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from threading import Thread
from typing import Any

from flask import Flask, jsonify, request
from flask.typing import ResponseReturnValue

from bot import message_processor
from core.text_utils import sanitize_untrusted_text
from webhook import chatwoot_signature
from webhook.http_hardening import RouteDecorator

logger = logging.getLogger(__name__)

CHATWOOT_INCOMING_MESSAGE_EVENT = "message_created"
CHATWOOT_MESSAGE_TYPE_INCOMING = "incoming"


def _should_process(event: dict[str, Any]) -> bool:
    """Return True only for new incoming non-private customer messages."""
    if event.get("event") != CHATWOOT_INCOMING_MESSAGE_EVENT:
        return False

    if event.get("message_type") != CHATWOOT_MESSAGE_TYPE_INCOMING:
        return False

    if event.get("private") is True:
        return False

    return True


def _run_in_background(event: dict[str, Any]) -> None:
    """Process the Chatwoot event off the request thread."""

    def worker() -> None:
        try:
            message_processor.process_chatwoot_message(event)
        except Exception as exc:
            logger.error(
                "Chatwoot background worker failed: %s",
                exc.__class__.__name__,
            )

    Thread(target=worker, daemon=True).start()


def register_chatwoot_routes(
    flask_app: Flask,
    webhook_rate_limit: RouteDecorator,
) -> None:
    """Attach the Chatwoot agent_bot POST handler to the given Flask app."""

    @flask_app.route("/chatwoot-webhook", methods=["POST"])
    @webhook_rate_limit
    def handle_chatwoot_event() -> ResponseReturnValue:
        """Process incoming Chatwoot agent-bot webhook events."""
        if not chatwoot_signature.verify_chatwoot_signature():
            return jsonify({"status": "invalid signature"}), 401

        if not request.is_json:
            return jsonify({"status": "unsupported content type"}), 415

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"status": "no data"}), 400

        if not _should_process(data):
            event_kind = sanitize_untrusted_text(str(data.get("event", "")), 32)
            message_type = sanitize_untrusted_text(str(data.get("message_type", "")), 32)
            logger.info(
                "Skipping Chatwoot event: event=%s, message_type=%s",
                event_kind or "missing",
                message_type or "missing",
            )
            return jsonify({"status": "ignored"}), 200

        _run_in_background(data)
        return jsonify({"status": "ok"}), 200
