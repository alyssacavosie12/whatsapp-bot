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
"""

from __future__ import annotations

from typing import Final

from core.text_utils import normalize_text

# Phrases that are unambiguous opt-out language. Matched as normalized
# substrings (after accent stripping and punctuation normalization).
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
_NOISE_ES: Final[frozenset[str]] = frozenset({"por", "favor", "porfavor", "ya", "ahora"})


def is_opt_out_request(text: str) -> tuple[bool, str | None, str | None]:
    """Return ``(matched, keyword, language)`` for opt-out detection.

    ``keyword`` is the keyword string that triggered the match (useful for
    auditing); ``language`` is ``"en"`` or ``"es"``. Returns
    ``(False, None, None)`` when no opt-out is detected.
    """
    if not text:
        return False, None, None

    cleaned = normalize_text(text)
    if not cleaned:
        return False, None, None

    tokens = cleaned.split()

    for keyword in OPT_OUT_PHRASES_EN:
        if keyword in cleaned:
            return True, keyword, "en"
    for keyword in OPT_OUT_PHRASES_ES:
        if keyword in cleaned:
            return True, keyword, "es"

    if len(tokens) <= MAX_TOKENS_FOR_SINGLE_WORD_MATCH:
        token_set = set(tokens)
        for keyword in OPT_OUT_SINGLE_WORDS_EN:
            if keyword in token_set and token_set.issubset({keyword, *_NOISE_EN}):
                return True, keyword, "en"
        for keyword in OPT_OUT_SINGLE_WORDS_ES:
            if keyword in token_set and token_set.issubset({keyword, *_NOISE_ES}):
                return True, keyword, "es"

    return False, None, None
