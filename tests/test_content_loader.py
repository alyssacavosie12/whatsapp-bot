from __future__ import annotations

import json
from typing import Any


def test_load_content_success(content_file: Any) -> None:
    from bot import content_loader

    data = content_loader.load_content()

    assert data["business_context"].startswith("You are the WhatsApp assistant")
    assert len(data["faq"]) == 3


def test_load_content_missing_file(tmp_path: Any, monkeypatch: Any) -> None:
    from bot import content_loader

    monkeypatch.setattr(content_loader, "CONTENT_FILE", tmp_path / "missing.json")
    content_loader.load_content.cache_clear()

    data = content_loader.load_content()

    assert data["business_context"] == "You are a helpful WhatsApp assistant."
    assert data["responses"] == {}
    assert data["faq"] == []


def test_load_content_invalid_json(tmp_path: Any, monkeypatch: Any) -> None:
    from bot import content_loader

    bad_file = tmp_path / "bot_content.json"
    bad_file.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(content_loader, "CONTENT_FILE", bad_file)
    content_loader.load_content.cache_clear()

    data = content_loader.load_content()

    assert data["faq"] == []


def test_load_content_root_must_be_object(tmp_path: Any, monkeypatch: Any) -> None:
    from bot import content_loader

    bad_file = tmp_path / "bot_content.json"
    bad_file.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    monkeypatch.setattr(content_loader, "CONTENT_FILE", bad_file)
    content_loader.load_content.cache_clear()

    data = content_loader.load_content()

    assert data["faq"] == []


def test_get_faq_entries_filters_invalid_items(tmp_path: Any, monkeypatch: Any) -> None:
    from bot import content_loader

    path = tmp_path / "bot_content.json"
    path.write_text(
        json.dumps({"business_context": "x", "responses": {}, "faq": [{"ok": True}, "bad", 123]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(content_loader, "CONTENT_FILE", path)
    content_loader.load_content.cache_clear()

    assert content_loader.get_faq_entries() == [{"ok": True}]


def test_detect_language(content_file: Any) -> None:
    from bot.content_loader import detect_language

    assert detect_language("hi there") == "en"
    assert detect_language("where are you located?") == "en"
    assert detect_language("hola") == "es"
    assert detect_language("¿cuánto cuesta botox?") == "es"
    assert detect_language("donde estan ubicados") == "es"


def test_get_response_language_fallback(content_file: Any) -> None:
    from bot.content_loader import get_response

    assert get_response("ai_fallback", "es").startswith("Fallback ES")
    assert get_response("ai_fallback", "en").startswith("Fallback EN")
    assert get_response("ai_fallback", "fr").startswith("Fallback EN")
    assert get_response("does_not_exist", "en") == ""


def test_get_response_handles_bad_responses_shape(tmp_path: Any, monkeypatch: Any) -> None:
    from bot import content_loader

    path = tmp_path / "bot_content.json"
    path.write_text(
        json.dumps({"business_context": "x", "responses": [], "faq": []}), encoding="utf-8"
    )
    monkeypatch.setattr(content_loader, "CONTENT_FILE", path)
    content_loader.load_content.cache_clear()

    assert content_loader.get_response("ai_fallback") == ""
