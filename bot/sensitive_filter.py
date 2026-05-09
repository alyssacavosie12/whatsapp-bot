"""Sensitive-message classification for privacy-preserving routing."""

from __future__ import annotations

import re
import unicodedata
from typing import Final

SENSITIVE_REDACTED_MESSAGE_TYPE: Final = "text_sensitive_redacted"

MEDICAL_SAFETY_RE: Final = re.compile(
    r"\b("
    r"pregnan(?:t|cy)|embarazad[ao]s?|embarazo|breastfeeding|lactat(?:e|ing)|lactancia|"
    r"allerg(?:y|ic|ies)|alerg(?:ia|ias|ico|ica)|contraindicat(?:ion|ions|ed)|"
    r"contraindicad[ao]s?|contraindicaciones|"
    r"medication|medicine|medicamento|medicina|antibiotic|antibiotico|"
    r"blood thinner(?:s)?|anticoagulant|anticoagulante|aspirin|warfarin|"
    r"diabetes|diabetic|diabetico|diabetica|hypertension|hipertension|"
    r"autoimmune|autoinmune|cancer|herpes|infection|infeccion|"
    r"rash|sarpullido|swelling|hinchazon|bruis(?:e|ing)|moreton|pain|dolor|"
    r"symptom|symptoms|sintoma|sintomas|diagnosis|diagnostico|"
    r"medical history|historial medico|medical condition|condicion medica|"
    r"side effect|side effects|efecto secundario|efectos secundarios"
    r")\b",
    re.IGNORECASE,
)

PROCEDURE_OR_CONCERN_RE: Final = re.compile(
    r"\b("
    r"botox|dysport|filler|fillers|relleno|rellenos|juvederm|radiesse|sculptra|"
    r"harmonyca|laser|co2|microneedling|micro(?:-|\s)?needling|blepharoplasty|"
    r"blefaroplastia|threads?|hilos|pdo|rhinomodeling|rinomodelacion|"
    r"lip|lips|labio|labios|forehead|frente|under eye|ojeras|wrinkle|wrinkles|"
    r"arruga|arrugas|skin|piel|acne|scar|scars|cicatriz|cicatrices|"
    r"face|cara|neck|cuello|body contour|contorno corporal"
    r")\b",
    re.IGNORECASE,
)

PERSONAL_INTENT_RE: Final = re.compile(
    r"\b("
    r"i|my|mine|myself|can i|could i|should i|i want|i need|i have|i am|"
    r"quiero|necesito|tengo|soy|estoy|puedo|podria|mi|mis|para mi|hacerme"
    r")\b",
    re.IGNORECASE,
)


def _fold_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii")


def classify_sensitive_message(text: str) -> str | None:
    """Return a sensitivity category when text should avoid AI and full storage."""
    normalized = " ".join(_fold_accents(str(text or "")).split())
    if not normalized:
        return None

    if MEDICAL_SAFETY_RE.search(normalized):
        return "medical_safety"

    if not PROCEDURE_OR_CONCERN_RE.search(normalized):
        return None

    if PERSONAL_INTENT_RE.search(normalized):
        return "aesthetic_consultation"

    return "aesthetic_service_interest"


def redacted_sensitive_body(category: str) -> str:
    """Return a non-content marker for sensitive inbox storage."""
    safe_category = re.sub(r"[^a-z0-9_-]", "", category.lower()) or "sensitive"
    return f"[sensitive message redacted: category={safe_category}]"
