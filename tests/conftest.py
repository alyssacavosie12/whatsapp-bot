from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


SAMPLE_CONTENT = {
    "business_context": (
        "You are the WhatsApp assistant for Tulum BTX / Tulum Botox. "
        "Never mention scooters, ATVs, car rentals, or Rent A Scooter Tulum."
    ),
    "responses": {
        "ai_fallback": {
            "en": "Fallback EN: Thanks for reaching out to Tulum BTX.",
            "es": "Fallback ES: Gracias por contactar a Tulum BTX.",
        },
        "media_response": {
            "en": "Media EN: A team member will review it shortly.",
            "es": "Media ES: Un miembro del equipo lo revisará pronto.",
        },
        "unknown_message": {
            "en": "Unknown EN: Please send us a text message.",
            "es": "Unknown ES: Envíanos un mensaje de texto.",
        },
        "human_handoff": {
            "en": "Human EN: A team member will get back to you.",
            "es": "Human ES: Un miembro del equipo te responderá.",
        },
    },
    "faq": [
        {
            "category": "General",
            "question": "Greeting",
            "keywords": ["hi", "hello", "hey", "hola", "buenos", "buenas"],
            "answer_en": "Hey there! Welcome to Tulum Botox.",
            "answer_es": "¡Hola! Bienvenido a Tulum Botox.",
        },
        {
            "category": "Pricing",
            "question": "How much does Botox/Dysport cost?",
            "keywords": ["botox cost", "botox price", "dysport cost", "price", "precio", "cuanto", "cuesta"],
            "answer_en": "Dysport is 135 MXN per unit.",
            "answer_es": "Dysport cuesta 135 MXN por unidad.",
        },
        {
            "category": "General",
            "question": "Where are you located?",
            "keywords": ["where", "location", "located", "ubicacion", "donde"],
            "answer_en": "We are located in Tulum Centro.",
            "answer_es": "Estamos ubicados en el Centro de Tulum.",
        },
    ],
}


@pytest.fixture()
def content_file(tmp_path, monkeypatch):
    """Point content_loader at a temporary bot_content.json."""
    from bot import content_loader

    path = tmp_path / "bot_content.json"
    path.write_text(json.dumps(SAMPLE_CONTENT, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(content_loader, "CONTENT_FILE", path)
    content_loader.load_content.cache_clear()

    yield path

    content_loader.load_content.cache_clear()
