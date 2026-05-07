"""FAQ matching for the WhatsApp bot.

FAQ entries live in bot_content.json so business answers can be changed without
editing the core webhook code.
"""

from __future__ import annotations

from typing import Any

from bot.content_loader import detect_language, get_faq_entries
from core.text_utils import normalize_text, text_tokens


# ─── JSON field names ────────────────────────────────────────

KEYWORDS_FIELD = "keywords"
QUESTION_FIELD = "question"
ANSWER_EN_FIELD = "answer_en"
ANSWER_ES_FIELD = "answer_es"
LEGACY_ANSWER_FIELD = "answer"


# ─── Matching scores ─────────────────────────────────────────

EXACT_MATCH_SCORE = 6
PHRASE_MATCH_SCORE = 4
TOKEN_MATCH_SCORE = 3
SUBSTRING_MATCH_SCORE = 1
QUESTION_TOKEN_SCORE = 1

DEFAULT_MATCH_THRESHOLD = 2
SHORT_MESSAGE_TOKEN_LIMIT = 3
SHORT_MESSAGE_THRESHOLD = 1
MIN_SUBSTRING_LENGTH = 4
MIN_QUESTION_TOKEN_LENGTH = 4


FAQEntry = dict[str, Any]


def _answer_for_language(entry: FAQEntry, lang: str) -> str:
    """Return Spanish answer when requested and available; otherwise English."""
    if lang == "es" and entry.get(ANSWER_ES_FIELD):
        return str(entry[ANSWER_ES_FIELD])

    return str(
        entry.get(ANSWER_EN_FIELD)
        or entry.get(LEGACY_ANSWER_FIELD)
        or ""
    )


def _score_keyword_match(message: str, message_tokens: set[str], keyword: str) -> int:
    """Score one keyword against a normalized user message."""
    if not keyword:
        return 0

    if message == keyword:
        return EXACT_MATCH_SCORE

    if " " in keyword and keyword in message:
        return PHRASE_MATCH_SCORE

    if keyword in message_tokens:
        return TOKEN_MATCH_SCORE

    if len(keyword) >= MIN_SUBSTRING_LENGTH and keyword in message:
        return SUBSTRING_MATCH_SCORE

    return 0


def _score_question_tokens(entry: FAQEntry, message_tokens: set[str]) -> int:
    """Give a small score boost when the user's words match FAQ question words."""
    question_tokens = text_tokens(entry.get(QUESTION_FIELD, ""))

    return sum(
        QUESTION_TOKEN_SCORE
        for token in question_tokens
        if len(token) >= MIN_QUESTION_TOKEN_LENGTH and token in message_tokens
    )


def _score_entry(entry: FAQEntry, message: str, message_tokens: set[str]) -> int:
    """Calculate the total match score for one FAQ entry."""
    keywords = entry.get(KEYWORDS_FIELD, [])

    if not isinstance(keywords, list):
        return 0

    score = 0

    for raw_keyword in keywords:
        keyword = normalize_text(raw_keyword)
        score += _score_keyword_match(message, message_tokens, keyword)

    score += _score_question_tokens(entry, message_tokens)

    return score


def _required_score(message_tokens: set[str], threshold: int) -> int:
    """Return lower threshold for very short direct messages like 'hi'."""
    if len(message_tokens) <= SHORT_MESSAGE_TOKEN_LIMIT:
        return SHORT_MESSAGE_THRESHOLD

    return threshold


def find_best_faq_match(
    user_message: str,
    threshold: int = DEFAULT_MATCH_THRESHOLD,
) -> str | None:
    """Return the best FAQ answer, or None if no confident match exists.

    Matching strategy:
    - exact keyword/message match is strongest
    - phrase match is strong
    - token match is medium
    - substring match is weak and only used for longer keywords

    This avoids the old issue where short messages like "hi" did not match
    because the score was divided by a long keyword list.
    """
    message = normalize_text(user_message)

    if not message:
        return None

    lang = detect_language(user_message)
    message_tokens = text_tokens(user_message)

    best_score = 0
    best_entry: FAQEntry | None = None

    for entry in get_faq_entries():
        if not isinstance(entry, dict):
            continue

        score = _score_entry(entry, message, message_tokens)

        if score > best_score:
            best_score = score
            best_entry = entry

    if best_entry and best_score >= _required_score(message_tokens, threshold):
        return _answer_for_language(best_entry, lang)

    return None


def faq_lookup(keyword: str) -> str | None:
    """Return the first FAQ answer with an exact keyword match.

    Kept for backwards compatibility with older app.py imports.
    """
    lang = detect_language(keyword)
    normalized_keyword = normalize_text(keyword)

    for entry in get_faq_entries():
        if not isinstance(entry, dict):
            continue

        keywords = entry.get(KEYWORDS_FIELD, [])

        if not isinstance(keywords, list):
            continue

        for raw_keyword in keywords:
            if normalized_keyword == normalize_text(raw_keyword):
                return _answer_for_language(entry, lang)

    return None