"""Health routes and generic Flask error handlers."""

from __future__ import annotations

from flask import Flask, jsonify
from flask.typing import ResponseReturnValue
from werkzeug.exceptions import RequestEntityTooLarge

from bot.ai_responder import anthropic_circuit_status
from core.cache import get_redis
from core.database import get_db_pool
from settings import INBOX_DATABASE_URL, INBOX_ENABLED, REDIS_URL


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
        """Return Railway health-check status with dependency details."""
        components: dict[str, str] = {
            "anthropic": anthropic_circuit_status(),
            "postgres": "disabled",
            "redis": "disabled",
        }
        overall_status = "ok"
        http_code = 200

        if REDIS_URL:
            try:
                get_redis(REDIS_URL).ping()
                components["redis"] = "ok"
            except Exception:
                components["redis"] = "degraded"
                overall_status = "degraded"

        if INBOX_ENABLED and INBOX_DATABASE_URL:
            try:
                with get_db_pool(INBOX_DATABASE_URL).connection() as conn:
                    conn.execute("SELECT 1")
                components["postgres"] = "ok"
            except Exception:
                components["postgres"] = "degraded"
                overall_status = "degraded"
                http_code = 503

        if components["anthropic"] == "circuit_open":
            overall_status = "degraded"

        return jsonify({"status": overall_status, "components": components}), http_code
