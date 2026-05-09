"""Detect WhatsApp opt-out keywords in EN/ES.

Required by:
- LFPDPPP (Mexico) ARCO `Oposición` — must honor opt-out without barriers.
- CCPA (California) — opt-out must be simple; "STOP" alone has to work.
- WhatsApp Business Policy — proactive opt-out reduces user "Block" actions
  and the resulting account-level complaint rate.

The detection is biased toward honoring opt-out intent: silencing a user who
didn't clearly mean to opt out is recoverable (they message again, an admin
can remove the opt-out record), but keeping a user on after they've objected
is a regulatory violation.

To reduce obvious false positives we:
- normalize accents ("DÉJAME" -> "dejame");
- require single-word keywords to appear only in very short messages and only
  alongside a tiny allowlist of "noise" tokens ("please", "por favor", etc.).

This module currently detects only English and Spanish opt-out language and
returns language codes limited to "en" or "es".
"""

from __future__ import annotations

from typing import Final, Literal

from core.text_utils import normalize_text

OptOutLanguage = Literal["en", "es"]
type OptOutMatch = tuple[bool, str | None, OptOutLanguage | None]

__all__ = [
    "OptOutLanguage",
    "OptOutMatch",
    "is_opt_out_request",
]

# Phrases that are unambiguous opt-out language. Matched as normalized
# substrings after accent stripping and punctuation normalization.
OPT_OUT_PHRASES_EN: Final[frozenset[str]] = frozenset(
    {
        "unsubscribe",
        "stop all",
        "stop messages",
        "stop texting",
        "stop texting me",
        "stop sending",
        "stop sending me",
        "stop messaging",
        "stop messaging me",
        "opt out",
        "opt-out",
        "optout",
        "remove me",
        "leave me alone",
        "do not contact",
        "do not message",
        "do not text",
        "don t contact",
        "don t message",
        "don t text",
        "no more messages",
        "no more texts",
    }
)

OPT_OUT_PHRASES_ES: Final[frozenset[str]] = frozenset(
    {
        "no molesten",
        "no molestar",
        "darme de baja",
        "darse de baja",
        "dar de baja",
        "no escriban",
        "no escribir",
        "no contactar",
        "no me contacten",
        "no me contactes",
        "no quiero mensajes",
        "dejame en paz",
        "dejen de escribirme",
        "deja de escribirme",
        "dejen de enviarme",
        "deja de enviarme",
        "dejen de enviar",
        "deja de enviar",
        "no mas mensajes",
    }
)

# Single tokens. Match only when the whole message is short and contains
# nothing but the keyword plus a tiny set of politeness/noise words.
OPT_OUT_SINGLE_WORDS_EN: Final[frozenset[str]] = frozenset(
    {
        "stop",
        "stopall",
        "end",
        "quit",
        "cancel",
        "dnd",
    }
)

OPT_OUT_SINGLE_WORDS_ES: Final[frozenset[str]] = frozenset(
    {
        "alto",
        "baja",
        "parar",
        "detener",
        "salir",
        "cancelar",
    }
)

MAX_TOKENS_FOR_SINGLE_WORD_MATCH: Final = 3

_NOISE_EN: Final[frozenset[str]] = frozenset({"please", "pls", "plz", "now"})
_NOISE_ES: Final[frozenset[str]] = frozenset(
    {
        "por",
        "favor",
        "porfavor",
        "ya",
        "ahora",
    }
)


def _phrase_match(
    cleaned: str,
    phrases: frozenset[str],
    language: OptOutLanguage,
) -> OptOutMatch:
    """Return an opt-out match for the first phrase contained in cleaned text."""
    for keyword in phrases:
        if keyword in cleaned:
            return True, keyword, language

    return False, None, None


def _single_word_match(
    token_set: set[str],
    keywords: frozenset[str],
    noise_words: frozenset[str],
    language: OptOutLanguage,
) -> OptOutMatch:
    """Return an opt-out match for short single-keyword messages."""
    for keyword in keywords:
        if keyword in token_set and token_set.issubset({keyword, *noise_words}):
            return True, keyword, language

    return False, None, None


def is_opt_out_request(text: str) -> OptOutMatch:
    """Return ``(matched, keyword, language)`` for opt-out detection.

    ``keyword`` is the keyword string that triggered the match and is useful
    for auditing. ``language`` is currently limited to ``"en"`` or ``"es"``.
    Returns ``(False, None, None)`` when no opt-out is detected.
    """
    if not text:
        return False, None, None

    cleaned = normalize_text(text)
    if not cleaned:
        return False, None, None

    en_phrase = _phrase_match(cleaned, OPT_OUT_PHRASES_EN, "en")
    if en_phrase[0]:
        return en_phrase

    es_phrase = _phrase_match(cleaned, OPT_OUT_PHRASES_ES, "es")
    if es_phrase[0]:
        return es_phrase

    tokens = cleaned.split()
    if len(tokens) > MAX_TOKENS_FOR_SINGLE_WORD_MATCH:
        return False, None, None

    token_set = set(tokens)

    en_single_word = _single_word_match(
        token_set,
        OPT_OUT_SINGLE_WORDS_EN,
        _NOISE_EN,
        "en",
    )
    if en_single_word[0]:
        return en_single_word

    return _single_word_match(
        token_set,
        OPT_OUT_SINGLE_WORDS_ES,
        _NOISE_ES,
        "es",
    )
