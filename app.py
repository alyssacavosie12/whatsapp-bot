"""Flask application factory for the WhatsApp bot."""

from __future__ import annotations

import logging
import os

from flask import Flask
from werkzeug.exceptions import RequestEntityTooLarge

from bot.chatwoot_config import chatwoot_transport_misconfiguration
from bot.processor_dependencies import (
    MessageProcessorDependencies,
    install_message_processor_dependencies,
)
from bot.whatsapp_client import warn_if_graph_api_version_deprecated
from core.database import DATABASE_OPERATION_ERRORS
from core.routes import handle_request_too_large, register_health_routes
from core.runtime import RuntimeDependencies, install_runtime_dependencies
from inbox.routes import register_admin_routes
from inbox.security import client_ip
from settings import (
    CHATWOOT_TRANSPORT,
    FLASK_SECRET_KEY,
    FORCE_HTTPS,
    INBOX_DATABASE_URL,
    INBOX_ENABLED,
    MAX_CONTENT_LENGTH,
    RATE_LIMIT_STORAGE_URL,
    WEBHOOK_RATE_LIMIT,
)
from webhook.chatwoot_routes import register_chatwoot_routes
from webhook.http_hardening import build_webhook_rate_limit, configure_talisman
from webhook.routes import register_webhook_routes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _initialize_runtime_pools(dependencies: RuntimeDependencies) -> None:
    """Initialize shared connection pools that are safe to create at startup."""
    if not INBOX_ENABLED or not INBOX_DATABASE_URL:
        return

    try:
        dependencies.database.initialize_pool(INBOX_DATABASE_URL)
        dependencies.database.initialize_pool(INBOX_DATABASE_URL, dict_rows=True)
    except DATABASE_OPERATION_ERRORS as exc:
        logger.error("Failed to initialize DB pool: %s", exc.__class__.__name__)


def _validate_chatwoot_configuration() -> None:
    """Fail loudly at boot if CHATWOOT_TRANSPORT is on but config is incomplete."""
    if not CHATWOOT_TRANSPORT:
        return

    misconfiguration = chatwoot_transport_misconfiguration()
    if misconfiguration:
        raise RuntimeError(misconfiguration)


def create_app(
    *,
    runtime_dependencies: RuntimeDependencies | None = None,
    message_dependencies: MessageProcessorDependencies | None = None,
) -> Flask:
    """Build and return a fully wired Flask application instance."""
    flask_app = Flask(__name__)
    flask_app.config.update(
        MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
        SECRET_KEY=FLASK_SECRET_KEY or os.urandom(32),
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    flask_app.debug = False
    dependencies = install_runtime_dependencies(flask_app, runtime_dependencies)
    if message_dependencies is not None:
        install_message_processor_dependencies(flask_app, message_dependencies)

    warn_if_graph_api_version_deprecated()
    _validate_chatwoot_configuration()
    _initialize_runtime_pools(dependencies)
    configure_talisman(flask_app, force_https=FORCE_HTTPS)
    webhook_rate_limit = build_webhook_rate_limit(
        flask_app,
        key_func=lambda: client_ip() or "unknown",
        rate_limit=WEBHOOK_RATE_LIMIT,
        storage_uri=RATE_LIMIT_STORAGE_URL,
    )

    register_health_routes(flask_app)
    register_admin_routes(flask_app)
    register_webhook_routes(flask_app, webhook_rate_limit)
    register_chatwoot_routes(flask_app, webhook_rate_limit)
    flask_app.register_error_handler(RequestEntityTooLarge, handle_request_too_large)

    return flask_app


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "127.0.0.1")
    create_app().run(host=host, port=port)
