from __future__ import annotations

from typing import Any


def test_short_english_greeting_matches(content_file: Any) -> None:
    from bot.faq import find_best_faq_match

    answer = find_best_faq_match("hi")

    assert answer == "Hey there! Welcome to Tulum Botox."


def test_short_spanish_greeting_matches(content_file: Any) -> None:
    from bot.faq import find_best_faq_match

    answer = find_best_faq_match("hola")

    assert answer == "¡Hola! Bienvenido a Tulum Botox."


def test_accented_spanish_query_matches_price(content_file: Any) -> None:
    from bot.faq import find_best_faq_match

    answer = find_best_faq_match("¿cuánto cuesta botox?")

    assert answer == "Dysport cuesta 135 MXN por unidad."


def test_english_price_query_matches(content_file: Any) -> None:
    from bot.faq import find_best_faq_match

    answer = find_best_faq_match("how much is botox price?")

    assert answer == "Dysport is 135 MXN per unit."


def test_location_query_matches(content_file: Any) -> None:
    from bot.faq import find_best_faq_match

    assert find_best_faq_match("where are you located?") == "We are located in Tulum Centro."
    assert find_best_faq_match("donde estan?") == "Estamos ubicados en el Centro de Tulum."


def test_unknown_query_returns_none(content_file: Any) -> None:
    from bot.faq import find_best_faq_match

    assert find_best_faq_match("do you rent scooters?") is None


def test_empty_query_returns_none(content_file: Any) -> None:
    from bot.faq import find_best_faq_match

    assert find_best_faq_match("") is None


def test_faq_lookup_exact_keyword(content_file: Any) -> None:
    from bot.faq import faq_lookup

    assert faq_lookup("hi") == "Hey there! Welcome to Tulum Botox."
    assert faq_lookup("hola") == "¡Hola! Bienvenido a Tulum Botox."
    assert faq_lookup("notakeyword") is None
