"""Load editable bot content from bot_content.json.

To update business context, FAQ answers, or canned responses, edit bot_content.json.

The core Python files should rarely need to change.

"""

from __future__ import annotations

import copy

import json

import logging

from functools import lru_cache

from pathlib import Path

from typing import Any

from core.text_utils import text_tokens

logger = logging.getLogger(__name__)

CONTENT_FILE = Path(__file__).with_name("bot_content.json")

# ─── JSON field names ────────────────────────────────────────

BUSINESS_CONTEXT_FIELD = "business_context"

RESPONSES_FIELD = "responses"

FAQ_FIELD = "faq"

EN_LANGUAGE = "en"

ES_LANGUAGE = "es"

# ─── Defaults ────────────────────────────────────────────────

DEFAULT_CONTENT: dict[str, Any] = {

    BUSINESS_CONTEXT_FIELD: "You are a helpful WhatsApp assistant.",

    RESPONSES_FIELD: {},

    FAQ_FIELD: [],

}

# ─── Text normalization ──────────────────────────────────────

SPANISH_MARKERS = {

    "hola",

    "gracias",

    "precio",

    "precios",

    "cuanto",

    "donde",

    "ubicacion",

    "cita",

    "agendar",

    "reservar",

    "reserva",

    "consulta",

    "relleno",

    "rellenos",

    "labios",

    "faciales",

    "tarjeta",

    "efectivo",

    "seguro",

    "duele",

    "dolor",

    "vuelo",

    "volar",

    "despues",

    "retoque",

    "lunares",

    "hilos",

    "nariz",

    "tratamiento",

    "tratamientos",

    "ubicados",

    "ubicada",

    "horario",

    "pago",

    "pagos",

}

def _default_content() -> dict[str, Any]:

    """Return a fresh copy of the default content object."""

    return copy.deepcopy(DEFAULT_CONTENT)

# ─── Content loading ─────────────────────────────────────────

@lru_cache(maxsize=1)

def load_content() -> dict[str, Any]:

    """Load bot content from JSON once per process."""

    try:

        with CONTENT_FILE.open("r", encoding="utf-8") as file:

            data = json.load(file)

    except FileNotFoundError:

        logger.error("bot_content.json not found")

        return _default_content()

    except json.JSONDecodeError as exc:

        logger.error("Invalid bot_content.json: %s", exc)

        return _default_content()

    if not isinstance(data, dict):

        logger.error("bot_content.json root must be a JSON object")

        return _default_content()

    return data

def get_business_context() -> str:

    """Return the system prompt/business context for the AI fallback."""

    return str(load_content().get(BUSINESS_CONTEXT_FIELD, "")).strip()

def get_faq_entries() -> list[dict[str, Any]]:

    """Return valid FAQ entries from bot_content.json."""

    entries = load_content().get(FAQ_FIELD, [])

    if not isinstance(entries, list):

        logger.error("bot_content.json field '%s' must be a list", FAQ_FIELD)

        return []

    return [entry for entry in entries if isinstance(entry, dict)]

# ─── Language / canned responses ─────────────────────────────

def detect_language(text: str) -> str:

    """Return 'es' for likely Spanish, otherwise 'en'.

    This is intentionally small and deterministic. It is only used to choose

    canned/FAQ response language, not for translation.

    """

    words = text_tokens(text)

    if words & SPANISH_MARKERS:

        return ES_LANGUAGE

    return EN_LANGUAGE

def get_response(name: str, language_hint: str = EN_LANGUAGE) -> str:

    """Return a canned response by name and language.

    Falls back to English, then to the first available non-empty value.

    """

    responses = load_content().get(RESPONSES_FIELD, {})

    if not isinstance(responses, dict):

        logger.error("bot_content.json field '%s' must be an object", RESPONSES_FIELD)

        return ""

    item = responses.get(name, "")

    if not isinstance(item, dict):

        return str(item or "")

    if item.get(language_hint):

        return str(item[language_hint])

    if item.get(EN_LANGUAGE):

        return str(item[EN_LANGUAGE])

    for value in item.values():

        if value:

            return str(value)

    return ""
