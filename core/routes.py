"""Health routes and generic Flask error handlers."""

from __future__ import annotations

from flask import Flask, jsonify
from flask.typing import ResponseReturnValue
from werkzeug.exceptions import RequestEntityTooLarge


def handle_request_too_large(_exc: RequestEntityTooLarge) -> ResponseReturnValue:
    """Convert Werkzeug's 413 into a JSON status the bot's clients expect."""
    return jsonify({"status": "payload too large"}), 413


def register_health_routes(flask_app: Flask) -> None:
    """Attach root and /health to the given Flask app."""

    @flask_app.route("/", methods=["GET"])
    def root() -> ResponseReturnValue:
        """Return a simple service status response."""
        return jsonify({"status": "ok", "service": "tulum-btx-whatsapp-bot"}), 200

    @flask_app.route("/health", methods=["GET"])
    def health() -> ResponseReturnValue:
        """Return the Railway health-check response."""
        return jsonify({"status": "healthy"}), 200
