"""Security helpers for the admin inbox HTTP surface."""

from __future__ import annotations

from flask import Response, request


def client_ip() -> str:
    """Return the best-effort client IP for audit records."""
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()

    return request.remote_addr or ""


def with_admin_security_headers(response: Response) -> Response:
    """Apply no-cache and browser hardening headers to admin responses."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; "
        "style-src 'unsafe-inline'; "
        "form-action 'self'; "
        "base-uri 'none'; "
        "frame-ancestors 'none'"
    )

    if request.headers.get("X-Forwarded-Proto", request.scheme) == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response


def admin_response(body: str, status: int = 200) -> Response:
    """Create an HTML admin response with security headers."""
    return with_admin_security_headers(
        Response(body, status=status, content_type="text/html; charset=utf-8")
    )


def inbox_auth_challenge() -> Response:
    """Ask the browser for admin inbox credentials."""
    response = admin_response("Unauthorized", 401)
    response.headers["WWW-Authenticate"] = 'Basic realm="Messages Inbox", charset="UTF-8"'
    return response
