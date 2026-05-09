"""Business-content tests against the real bot_content.json.

These verify what customers actually receive on real questions —
Allergan/Dysport branding, Sculptra-as-biostimulator, CO2-vs-hair-removal,
price accuracy, medical-question routing. They guard the business
constraints the team relies on so that a careless edit to bot_content.json
fails CI rather than ships.

Tests run against the real `bot_content.json` (via the `real_content`
fixture), not the synthetic SAMPLE_CONTENT used by the FAQ-matcher tests.
"""

from __future__ import annotations

import re


def test_botox_brand_question_mentions_both_brands(real_content):
    """The brand answer must list both Allergan and Dysport."""
    from bot.faq import find_best_faq_match

    answer = find_best_faq_match("What brand of botox do you use?")

    assert answer, "No FAQ match for the Botox-brand question"
    lower = answer.lower()
    assert "allergan" in lower
    assert "dysport" in lower


def test_botox_is_described_as_neurotoxin_not_filler(real_content):
    """The Botox-brand answer must classify Botox as a neurotoxin, never a filler."""
    from bot.faq import find_best_faq_match

    answer = find_best_faq_match("What brand of botox do you use?")
    lower = answer.lower()

    assert "neurotoxin" in lower
    assert "filler" not in lower, (
        "Botox-brand answer must not call Botox a filler — it's a neurotoxin"
    )


def test_sculptra_is_described_as_biostimulator_not_filler(real_content):
    """Sculptra is a collagen biostimulator — must not be sold as a traditional filler."""
    from bot.faq import find_best_faq_match

    answer = find_best_faq_match("What is Sculptra?")
    lower = answer.lower()

    assert "biostimulator" in lower or "bioestimulador" in lower

    if "filler" in lower:
        # The word `filler` is allowed only in negative/contrasting context.
        for match in re.finditer(r"\bfillers?\b", lower):
            window = lower[max(0, match.start() - 40) : match.start()]
            assert "different from" in window or "not a" in window or "not traditional" in window, (
                f"'filler' appears without a contrasting qualifier: "
                f"...{lower[max(0, match.start() - 40) : match.end() + 10]}..."
            )


def test_co2_laser_is_not_described_as_hair_removal(real_content):
    """CO2 laser is skin resurfacing — `hair removal` may appear only when negated."""
    from bot.faq import find_best_faq_match

    answer = find_best_faq_match("What is CO2 laser?")
    lower = answer.lower()

    assert "resurfacing" in lower

    for match in re.finditer(r"hair removal", lower):
        window = lower[max(0, match.start() - 30) : match.start()]
        assert "not" in window, (
            f"'hair removal' mentioned without negation: "
            f"...{lower[max(0, match.start() - 30) : match.end() + 10]}..."
        )


def test_botox_price_is_135_mxn_per_unit(real_content):
    """The Botox/Dysport pricing answer must read 135 MXN per unit."""
    from bot.faq import find_best_faq_match

    answer = find_best_faq_match("How much is botox per unit?")

    assert answer, "No FAQ match for the Botox price question"
    assert "135" in answer
    assert "mxn" in answer.lower(), "Price must be quoted in MXN, not USD"


def test_business_context_redirects_medical_questions_to_consultation(real_content):
    """Pregnancy/allergies aren't separate FAQs — the AI must route them via business_context.

    There is no dedicated FAQ entry for medical safety questions, so they
    fall through to the AI fallback. The fallback only redirects safely if
    `business_context` tells the model — in the *same instruction* as the
    pregnancy mention — to send these customers to the booking URL.
    """
    from bot.content_loader import get_business_context

    ctx = get_business_context().lower()

    assert "pregnan" in ctx, "business_context must mention pregnancy"

    # Split into sentences and find the one(s) mentioning pregnancy.
    sentences = re.split(r"(?<=[.!?])\s+", ctx)
    pregnancy_sentences = [s for s in sentences if "pregnan" in s]

    assert pregnancy_sentences, "no sentence mentions pregnancy"
    assert any("tulumbotox.com/book" in s for s in pregnancy_sentences), (
        "the pregnancy instruction must redirect to tulumbotox.com/book in "
        f"the same sentence; sentences found: {pregnancy_sentences}"
    )
