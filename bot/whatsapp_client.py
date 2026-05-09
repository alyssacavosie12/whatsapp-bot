"""WhatsApp Cloud API client helpers."""

from __future__ import annotations

import email.utils
import logging
import time
from datetime import UTC, datetime
from typing import Final

import requests

from core.phone_utils import is_valid_phone, mask_phone, normalize_phone
from core.sender_id import is_valid_recipient
from settings import (
    GRAPH_API_VERSION,
    TEAM_NOTIFY_PHONE,
    WHATSAPP_MAX_RETRIES,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_REQUEST_TIMEOUT_SECONDS,
    WHATSAPP_RETRY_BACKOFF_SECONDS,
    WHATSAPP_TOKEN,
)
from webhook.graph_api import summarize_graph_error

logger = logging.getLogger(__name__)

RETRYABLE_WHATSAPP_STATUSES: Final = {429, 500, 502, 503, 504}
RATE_LIMIT_STATUS: Final = 429
SUCCESS_STATUS: Final = 200

GRAPH_API_BASE: Final = "https://graph.facebook.com"

# Guardrail for hostile or malformed Retry-After values.
MAX_RETRY_AFTER_SECONDS: Final = 300.0

# Header names observed across Meta/Gateway layers. Header lookup in requests
# is case-insensitive, but keeping likely variants here makes intent obvious.
REQUEST_ID_HEADERS: Final[tuple[str, ...]] = (
    "x-fb-request-id",
    "x-business-use-case-usage",
    "x-fb-trace-id",
)

# Versions Meta has formally deprecated. The check is intentionally a static
# allowlist instead of a network call: deploy-time hint, not runtime gate.
# Update this list whenever Meta publishes a new deprecation in the Graph API
# changelog (https://developers.facebook.com/docs/graph-api/changelog).
DEPRECATED_GRAPH_API_VERSIONS: Final[frozenset[str]] = frozenset(
    {
        "v17.0",
        "v18.0",
        "v19.0",
        "v20.0",
        "v21.0",  # deprecated 2026-01-26
        "v22.0",  # deprecated 2026-05-21
    }
)


def whatsapp_messages_url() -> str:
    """Return the Graph API messages endpoint for the configured number.

    The URL is built lazily so monkeypatching `GRAPH_API_VERSION` in tests or
    rotating it via the environment takes effect on the next call without
    re-importing the module.
    """
    return f"{GRAPH_API_BASE}/{GRAPH_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"


def warn_if_graph_api_version_deprecated() -> None:
    """Log a warning when GRAPH_API_VERSION matches a Meta-deprecated version.

    Called once at app startup. Keeps deployment honest without making a
    network round-trip every boot.
    """
    if GRAPH_API_VERSION in DEPRECATED_GRAPH_API_VERSIONS:
        logger.warning(
            "Graph API %s is deprecated by Meta; bump GRAPH_API_VERSION "
            "(see developers.facebook.com/docs/graph-api/changelog)",
            GRAPH_API_VERSION,
        )


def notify_team(message: str) -> None:
    """Send an alert to the team WhatsApp number."""
    if TEAM_NOTIFY_PHONE:
        send_whatsapp_message(TEAM_NOTIFY_PHONE, message)
        logger.info("Team notified")
    else:
        logger.info("TEAM_NOTIFY_PHONE not set; team notification skipped")


def _request_context(response: requests.Response) -> str:
    """Return stable request-id context from Meta response headers when present."""
    parts: list[str] = []
    headers = getattr(response, "headers", {}) or {}

    for header in REQUEST_ID_HEADERS:
        value = headers.get(header) if hasattr(headers, "get") else None
        if value:
            parts.append(f"{header}={value}")

    return " ".join(parts) or "request_id=unavailable"


def _retry_after_seconds(response: requests.Response) -> float | None:
    """Return a safe Retry-After delay in seconds for 429 responses.

    Supports both standard formats:
    - integer/float seconds
    - HTTP-date
    """
    raw_retry_after = response.headers.get("Retry-After")
    if not raw_retry_after:
        return None

    value = raw_retry_after.strip()
    if not value:
        return None

    try:
        delay = float(value)
    except ValueError:
        try:
            retry_at = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None

        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)

        delay = (retry_at - datetime.now(UTC)).total_seconds()

    if delay < 0:
        return None

    if delay > MAX_RETRY_AFTER_SECONDS:
        logger.debug(
            "Ignoring excessive Retry-After from WhatsApp: retry_after=%s max=%s",
            delay,
            MAX_RETRY_AFTER_SECONDS,
        )
        return None

    return delay


def _backoff_delay_seconds(attempt: int) -> float:
    """Return exponential backoff delay."""
    return float(WHATSAPP_RETRY_BACKOFF_SECONDS) * float(2 ** max(0, attempt - 1))


def _sleep_before_retry(
    attempt: int,
    max_attempts: int,
    response: requests.Response | None = None,
) -> None:
    """Sleep with Retry-After-aware exponential backoff unless no attempts remain."""
    if attempt >= max_attempts:
        return

    if response is not None and response.status_code == RATE_LIMIT_STATUS:
        retry_after = _retry_after_seconds(response)
        if retry_after is not None:
            logger.debug(
                "Using WhatsApp Retry-After before retry: retry_after=%s attempt=%s",
                retry_after,
                attempt,
            )
            time.sleep(retry_after)
            return

    time.sleep(_backoff_delay_seconds(attempt))


def _normalized_recipient(to_recipient: str) -> str | None:
    """Return a normalized phone or BSUID recipient, or None when invalid."""
    normalized = normalize_phone(to_recipient)
    if normalized and is_valid_phone(normalized):
        return normalized

    if is_valid_recipient(to_recipient):
        return to_recipient

    return None


def send_whatsapp_message(to_recipient: str, text: str) -> requests.Response | None:
    """Send a text message through the WhatsApp Cloud API with transient retries.

    ``to_recipient`` may be an E.164 phone number or a Business-Scoped User ID
    (BSUID, post June 2026). Phones are normalized; BSUIDs are passed through
    verbatim. Anything else is rejected before the network call.
    """
    if not WHATSAPP_TOKEN:
        logger.error("WHATSAPP_TOKEN is not set")
        return None

    if not WHATSAPP_PHONE_NUMBER_ID:
        logger.error("WHATSAPP_PHONE_NUMBER_ID is not set")
        return None

    if not to_recipient:
        logger.error("Cannot send message: recipient id is empty")
        return None

    to_phone = _normalized_recipient(to_recipient)
    if to_phone is None:
        logger.error("Cannot send message: recipient id is invalid")
        return None

    url = whatsapp_messages_url()
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text},
    }

    max_attempts = max(1, WHATSAPP_MAX_RETRIES)
    last_response: requests.Response | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=WHATSAPP_REQUEST_TIMEOUT_SECONDS,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            logger.warning(
                "WhatsApp send transient error: attempt=%s error=%s",
                attempt,
                exc.__class__.__name__,
            )
            _sleep_before_retry(attempt, max_attempts)
            continue
        except requests.RequestException as exc:
            logger.error("Failed to send message request: %s", exc.__class__.__name__)
            return None

        last_response = response
        request_context = _request_context(response)

        if response.status_code == SUCCESS_STATUS:
            logger.info("Message sent to %s", mask_phone(to_phone))
            logger.debug("WhatsApp send success context: %s", request_context)
            return response

        if response.status_code not in RETRYABLE_WHATSAPP_STATUSES:
            logger.error(
                "Failed to send message: status=%s, graph_error=%s, context=%s",
                response.status_code,
                summarize_graph_error(response),
                request_context,
            )
            return response

        logger.warning(
            "WhatsApp send retry: attempt=%s status=%s context=%s",
            attempt,
            response.status_code,
            request_context,
        )
        _sleep_before_retry(attempt, max_attempts, response)

    if last_response is not None:
        logger.error(
            "WhatsApp send exhausted retries for %s: status=%s graph_error=%s context=%s",
            mask_phone(to_phone),
            last_response.status_code,
            summarize_graph_error(last_response),
            _request_context(last_response),
        )
    else:
        logger.error("WhatsApp send exhausted retries for %s", mask_phone(to_phone))

    return last_response
