"""Sensitive-message classification for privacy-preserving routing."""

from __future__ import annotations

import re
import unicodedata
from typing import Final, Literal

SENSITIVE_REDACTED_MESSAGE_TYPE: Final = "text_sensitive_redacted"

MEDICAL_SAFETY_CATEGORY: Final = "medical_safety"
AESTHETIC_CONSULTATION_CATEGORY: Final = "aesthetic_consultation"
AESTHETIC_SERVICE_INTEREST_CATEGORY: Final = "aesthetic_service_interest"

SensitiveCategory = Literal[
    "medical_safety",
    "aesthetic_consultation",
    "aesthetic_service_interest",
]

__all__ = [
    "AESTHETIC_CONSULTATION_CATEGORY",
    "AESTHETIC_SERVICE_INTEREST_CATEGORY",
    "MEDICAL_SAFETY_CATEGORY",
    "SENSITIVE_REDACTED_MESSAGE_TYPE",
    "SensitiveCategory",
    "classify_sensitive_message",
    "redacted_sensitive_body",
]

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
    """Return ASCII text with accents removed."""
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii")


def classify_sensitive_message(text: str) -> SensitiveCategory | None:
    """Return a sensitivity category when text should avoid AI and full storage.

    Medical safety indicators always take precedence over aesthetic procedure
    terms. This ensures messages mentioning risks, symptoms, pregnancy,
    medications, allergies, or contraindications are routed to human handoff
    even if they also mention Botox/fillers/etc.
    """
    normalized = " ".join(_fold_accents(str(text or "")).split())
    if not normalized:
        return None

    if MEDICAL_SAFETY_RE.search(normalized):
        return MEDICAL_SAFETY_CATEGORY

    if not PROCEDURE_OR_CONCERN_RE.search(normalized):
        return None

    if PERSONAL_INTENT_RE.search(normalized):
        return AESTHETIC_CONSULTATION_CATEGORY

    return AESTHETIC_SERVICE_INTEREST_CATEGORY


def redacted_sensitive_body(category: str) -> str:
    """Return a non-content marker for sensitive inbox storage."""
    safe_category = re.sub(r"[^a-z0-9_-]", "", category.lower()) or "sensitive"
    return f"[sensitive message redacted: category={safe_category}]"
