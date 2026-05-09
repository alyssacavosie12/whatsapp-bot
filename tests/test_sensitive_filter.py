from __future__ import annotations

from typing import Any

import pytest

from bot.sensitive_filter import classify_sensitive_message, redacted_sensitive_body


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("I am pregnant, can I get Botox?", "medical_safety"),
        ("Tengo alergia a lidocaina", "medical_safety"),
        ("Tengo hipertensión e infección", "medical_safety"),
        ("Can I do filler while taking blood thinners?", "medical_safety"),
        ("Quiero botox para mis arrugas", "aesthetic_consultation"),
        ("I need lip filler under my eyes", "aesthetic_consultation"),
        ("botox price", "aesthetic_service_interest"),
        ("Do you offer Dysport?", "aesthetic_service_interest"),
    ],
)
def test_classify_sensitive_message_detects_medical_and_personal_aesthetic(
    text: Any,
    category: Any,
) -> None:
    assert classify_sensitive_message(text) == category


@pytest.mark.parametrize(
    "text",
    [
        "where are you located?",
        "what are your hours?",
        "hello",
    ],
)
def test_classify_sensitive_message_allows_general_faq_questions(text: Any) -> None:
    assert classify_sensitive_message(text) is None


def test_redacted_sensitive_body_contains_only_category_marker() -> None:
    body = redacted_sensitive_body("medical_safety")

    assert body == "[sensitive message redacted: category=medical_safety]"
