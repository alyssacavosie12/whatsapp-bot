"""Meta WhatsApp webhook routes."""

from __future__ import annotations

import hmac
import logging
from typing import Any, cast

from flask import Flask, jsonify, request
from flask.typing import ResponseReturnValue

from bot import message_processor
from core.text_utils import sanitize_untrusted_text
from settings import VERIFY_TOKEN
from webhook import signature as webhook_signature
from webhook.events import iter_webhook_messages
from webhook.http_hardening import RouteDecorator
from webhook.schema import validate_webhook_payload

logger = logging.getLogger(__name__)


def register_webhook_routes(flask_app: Flask, webhook_rate_limit: RouteDecorator) -> None:
    """Attach the GET verification and POST event handlers to the given Flask app."""

    @flask_app.route("/webhook", methods=["GET"])
    def verify_webhook() -> ResponseReturnValue:
        """Respond to Meta's webhook URL verification challenge."""
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token", "")
        challenge = request.args.get("hub.challenge")

        if not VERIFY_TOKEN:
            logger.error("VERIFY_TOKEN is not set; refusing webhook verification")
            return "Forbidden", 403

        if mode == "subscribe" and hmac.compare_digest(
            token.encode("utf-8"), VERIFY_TOKEN.encode("utf-8")
        ):
            logger.info("Webhook verified successfully")
            return challenge or "", 200

        logger.warning("Webhook verification failed")
        return "Forbidden", 403

    @flask_app.route("/webhook", methods=["POST"])
    @webhook_rate_limit
    def handle_message() -> ResponseReturnValue:
        """Process incoming WhatsApp webhook events."""
        if not webhook_signature.verify_meta_signature():
            return jsonify({"status": "invalid signature"}), 401

        if not request.is_json:
            return jsonify({"status": "unsupported content type"}), 415

        data = request.get_json(silent=True)

        if not data:
            return jsonify({"status": "no data"}), 400

        payload_ok, payload_error = validate_webhook_payload(data)
        if not payload_ok:
            logger.warning(
                "Invalid webhook payload rejected: %s",
                sanitize_untrusted_text(payload_error, 120),
            )
            return jsonify({"status": "invalid payload"}), 400

        try:
            payload = cast(dict[str, Any], data)
            events = list(iter_webhook_messages(payload))

            if not events:
                return jsonify({"status": "no messages"}), 200

            statuses: list[str] = []

            for value, message in events:
                try:
                    statuses.append(message_processor.process_webhook_message(value, message))
                except Exception as exc:
                    logger.error("Error processing message: %s", exc.__class__.__name__)
                    statuses.append("ok")

            if len(statuses) == 1 and statuses[0] != "ok":
                return jsonify({"status": statuses[0]}), 200

        except Exception as exc:
            logger.error("Error processing webhook: %s", exc.__class__.__name__)

        return jsonify({"status": "ok"}), 200
