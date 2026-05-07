"""Detect WhatsApp opt-out keywords in EN/ES.

Required by:
- LFPDPPP (Mexico) ARCO `Oposición` — must honor opt-out without barriers.
- CCPA (California) — opt-out must be simple; "STOP" alone has to work.
- WhatsApp Business Policy — proactive opt-out reduces user "Block" actions
  and the resulting account-level complaint rate.

The detection is biased toward false positives: silencing a user who didn't
clearly mean to opt out is recoverable (they message again, an admin can
remove the opt-out record), but keeping a user on after they've objected is
a regulatory violation. We compensate by limiting single-word keywords to
very short messages so "stop the rain" and "soy alto" don't trigger.
"""

from __future__ import annotations

import re
from typing import Final

# Phrases that are unambiguous opt-out language. Match anywhere in messages
# of up to MAX_TOKENS_FOR_PHRASE_MATCH tokens.
OPT_OUT_PHRASES_EN: Final[frozenset[str]] = frozenset(
    {
        "unsubscribe",
        "opt out",
        "opt-out",
        "remove me",
        "stop messages",
        "stop messaging",
        "stop sending",
        "stop texting",
        "leave me alone",
        "do not contact",
        "do not message",
        "no more messages",
    }
)
OPT_OUT_PHRASES_ES: Final[frozenset[str]] = frozenset(
    {
        "no molesten",
        "no molestar",
        "darme de baja",
        "darse de baja",
        "no escriban",
        "no escribir",
        "no contactar",
        "no quiero mensajes",
        "dejame en paz",
        "dejen de escribirme",
    }
)

# Single tokens. Match only when the whole message is short
# (≤ MAX_TOKENS_FOR_SINGLE_WORD_MATCH) so "stop the rain" or "soy alto"
# don't accidentally opt the user out.
OPT_OUT_SINGLE_WORDS_EN: Final[frozenset[str]] = frozenset({"stop", "cancel", "dnd"})
OPT_OUT_SINGLE_WORDS_ES: Final[frozenset[str]] = frozenset({"baja", "detener", "alto"})

MAX_TOKENS_FOR_PHRASE_MATCH: Final = 8
MAX_TOKENS_FOR_SINGLE_WORD_MATCH: Final = 2

_PUNCTUATION_RE: Final = re.compile(r"[^a-z\s\-]")
_WHITESPACE_RE: Final = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation/control chars, collapse whitespace."""
    cleaned = _PUNCTUATION_RE.sub(" ", text.lower().strip())
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def is_opt_out_request(text: str) -> tuple[bool, str | None, str | None]:
    """Return ``(matched, keyword, language)`` for opt-out detection.

    ``keyword`` is the keyword string that triggered the match (useful for
    auditing); ``language`` is ``"en"`` or ``"es"``. Returns
    ``(False, None, None)`` when no opt-out is detected.
    """
    if not text:
        return False, None, None

    cleaned = _normalize(text)
    if not cleaned:
        return False, None, None

    tokens = cleaned.split()
    if len(tokens) > MAX_TOKENS_FOR_PHRASE_MATCH:
        return False, None, None

    for keyword in OPT_OUT_PHRASES_EN:
        if keyword in cleaned:
            return True, keyword, "en"
    for keyword in OPT_OUT_PHRASES_ES:
        if keyword in cleaned:
            return True, keyword, "es"

    if len(tokens) <= MAX_TOKENS_FOR_SINGLE_WORD_MATCH:
        token_set = set(tokens)
        for keyword in OPT_OUT_SINGLE_WORDS_EN:
            if keyword in token_set:
                return True, keyword, "en"
        for keyword in OPT_OUT_SINGLE_WORDS_ES:
            if keyword in token_set:
                return True, keyword, "es"

    return False, None, None
