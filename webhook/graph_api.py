"""Small helpers for Meta Graph API interactions."""

from __future__ import annotations

import requests

from core.text_utils import sanitize_untrusted_text

GRAPH_ERROR_FIELDS = ("code", "error_subcode", "type", "fbtrace_id")


def summarize_graph_error(response: requests.Response) -> str:
    """Summarize Graph API errors without persisting response bodies or PII."""
    try:
        body = response.json()
    except (AttributeError, ValueError):
        return "body omitted"

    if not isinstance(body, dict) or not isinstance(body.get("error"), dict):
        return "body omitted"

    error = body["error"]
    fields = [
        f"{field}={sanitize_untrusted_text(error[field], 80)}"
        for field in GRAPH_ERROR_FIELDS
        if error.get(field)
    ]

    return ", ".join(fields) or "body omitted"
