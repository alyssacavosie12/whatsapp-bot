"""HTTP security middleware setup for the Flask app."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import cast

from flask import Flask
from flask.typing import ResponseReturnValue

logger = logging.getLogger(__name__)
RouteHandler = Callable[..., ResponseReturnValue]
RouteDecorator = Callable[[RouteHandler], RouteHandler]


def _identity_decorator(func: RouteHandler) -> RouteHandler:
    """Return a route handler unchanged when a limiter is unavailable."""
    return func


def configure_talisman(flask_app: Flask, *, force_https: bool) -> None:
    """Apply global browser hardening headers when Flask-Talisman is installed."""
    try:
        from flask_talisman import Talisman
    except ImportError:
        logger.warning("flask-talisman is not installed; global headers disabled")
        return

    csp = {
        "default-src": ["'self'"],
        "script-src": ["'self'"],
        "style-src": ["'self'", "'unsafe-inline'"],
        "object-src": ["'none'"],
        "base-uri": ["'none'"],
        "frame-ancestors": ["'none'"],
    }
    Talisman(
        flask_app,
        force_https=force_https,
        strict_transport_security=force_https,
        strict_transport_security_max_age=31536000,
        content_security_policy=csp,
        frame_options="DENY",
        referrer_policy="strict-origin-when-cross-origin",
        session_cookie_secure=True,
        session_cookie_http_only=True,
        session_cookie_samesite="Lax",
    )


def build_webhook_rate_limit(
    flask_app: Flask,
    *,
    key_func: Callable[[], str],
    rate_limit: str,
    storage_uri: str,
) -> RouteDecorator:
    """Return a route decorator for the webhook IP rate limit."""
    if not rate_limit:
        return _identity_decorator

    try:
        from flask_limiter import Limiter
    except ImportError:
        logger.warning("flask-limiter is not installed; webhook IP limit disabled")
        return _identity_decorator

    limiter = Limiter(
        key_func=key_func,
        app=flask_app,
        default_limits=[],
        storage_uri=storage_uri or "memory://",
    )
    return cast(RouteDecorator, limiter.limit(rate_limit))
