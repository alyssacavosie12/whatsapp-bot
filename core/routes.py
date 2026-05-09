"""Health routes and generic Flask error handlers."""

from __future__ import annotations

from flask import Flask, Response, jsonify
from flask.typing import ResponseReturnValue
from werkzeug.exceptions import RequestEntityTooLarge

from bot.ai_responder import anthropic_circuit_status
from core.cache import REDIS_OPERATION_ERRORS, get_redis
from core.database import DATABASE_OPERATION_ERRORS, get_db_pool
from core.privacy_notice import privacy_notice_html
from settings import INBOX_DATABASE_URL, INBOX_ENABLED, REDIS_URL

SERVICE_NAME = "tulum-btx-whatsapp-bot"

ComponentStatus = dict[str, str]


def handle_request_too_large(_exc: RequestEntityTooLarge) -> ResponseReturnValue:
    """Convert Werkzeug's 413 into a JSON status the bot's clients expect."""
    return jsonify({"status": "payload too large"}), 413


def _redis_health_status() -> str:
    """Return Redis dependency status for readiness checks.

    Redis is treated as non-critical for HTTP status: if it is down, the service
    can still answer webhook requests, but rate-limit/dedup/cache behavior may
    be degraded.
    """
    if not REDIS_URL:
        return "disabled"

    try:
        get_redis(REDIS_URL).ping()
    except REDIS_OPERATION_ERRORS:
        return "degraded"

    return "ok"


def _postgres_health_status() -> str:
    """Return Postgres dependency status for readiness checks.

    Postgres is critical when the inbox is enabled because inbound message
    persistence, audit records, opt-out proof, and admin inbox behavior depend
    on it.
    """
    if not INBOX_ENABLED or not INBOX_DATABASE_URL:
        return "disabled"

    try:
        with get_db_pool(INBOX_DATABASE_URL).connection() as conn:
            conn.execute("SELECT 1")
    except DATABASE_OPERATION_ERRORS:
        return "degraded"

    return "ok"


def _anthropic_health_status() -> str:
    """Return Anthropic dependency status for readiness checks."""
    return anthropic_circuit_status()


def _overall_health_status(components: ComponentStatus) -> tuple[str, int]:
    """Return overall service status and HTTP code.

    Liveness remains lightweight at ``/``. This readiness endpoint returns
    dependency details. Non-critical degradation returns HTTP 200 with
    ``status=degraded``; critical dependency failure returns HTTP 503.
    """
    if components["postgres"] == "degraded":
        return "degraded", 503

    if any(status == "degraded" for status in components.values()):
        return "degraded", 200

    if components["anthropic"] == "circuit_open":
        return "degraded", 200

    return "ok", 200


def register_health_routes(flask_app: Flask) -> None:
    """Attach liveness, privacy, and readiness routes to the given Flask app."""

    @flask_app.route("/", methods=["GET"])
    def root() -> ResponseReturnValue:
        """Return a lightweight liveness status without dependency checks."""
        return jsonify({"status": "ok", "service": SERVICE_NAME}), 200

    @flask_app.route("/privacy", methods=["GET"])
    def privacy() -> ResponseReturnValue:
        """Return the public Privacy Notice."""
        return Response(
            privacy_notice_html(),
            status=200,
            content_type="text/html; charset=utf-8",
        )

    @flask_app.route("/health", methods=["GET"])
    def health() -> ResponseReturnValue:
        """Return readiness status with dependency details."""
        components: ComponentStatus = {
            "anthropic": _anthropic_health_status(),
            "postgres": _postgres_health_status(),
            "redis": _redis_health_status(),
        }
        overall_status, http_code = _overall_health_status(components)

        return jsonify({"status": overall_status, "components": components}), http_code
