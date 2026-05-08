"""Hallucination guards: pin business_context rules and FAQ copy.

Hallucination defenses live in two places:

- The system prompt sent to Claude (`business_context`) tells the model
  to never guarantee results, never invent information, only answer from
  the content in this file plus the FAQ, and redirect unknown questions
  to the booking URL.
- The static FAQ answers in `bot_content.json` themselves stay free of
  unconditional promises ("guaranteed", "permanent results", "no risk").

These tests pin both. They do not prove the model obeys the prompt — that
is a behavioral guarantee from Anthropic, verifiable only with an opt-in
live canary — but they fail CI when someone editing `bot_content.json`
removes a guardrail phrase or adds promising copy that contradicts it.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

FORBIDDEN_FAQ_PHRASES = [
    "guarantee",
    "guaranteed",
    "definitely will",
    "permanent results",
    "no risk",
    "risk-free",
    "miraculous",
]


# ─── business_context guardrails ──────────────────────────────────────


def test_business_context_forbids_guaranteeing_or_inventing(real_content):
    """The system prompt must explicitly forbid guarantees and invention."""
    from bot.content_loader import get_business_context

    ctx = get_business_context().lower()

    assert "never guarantee" in ctx, "business_context must forbid result guarantees"
    assert "invent" in ctx, (
        "business_context must forbid inventing information when an answer isn't in the file"
    )


def test_business_context_restricts_ai_to_known_content(real_content):
    """The system prompt must scope the model to bot_content.json + FAQ.

    Without this rule, when asked about a treatment not listed (e.g.
    blepharoplasty), the model can invent a price. With it, the safe
    default is "I don't have that information; please book a consultation".
    """
    from bot.content_loader import get_business_context

    ctx = get_business_context().lower()

    assert "only the information" in ctx or "only use the information" in ctx, (
        "business_context must constrain the model to known content"
    )


def test_business_context_redirects_unknown_questions_to_booking(real_content):
    """The system prompt must surface the booking URL as the redirect target.

    The booking URL is mentioned multiple times for different reasons (FAQ
    answers, medical-question redirect, etc). At minimum one of those
    instructions must point at tulumbotox.com/book — otherwise the model
    has no canonical destination for "I don't know" answers.
    """
    from bot.content_loader import get_business_context

    ctx = get_business_context().lower()

    assert "tulumbotox.com/book" in ctx
    assert "consultation" in ctx or "book a" in ctx


# ─── FAQ content audit ────────────────────────────────────────────────


@pytest.mark.parametrize("phrase", FORBIDDEN_FAQ_PHRASES)
def test_no_faq_answer_contains_unconditional_promise(real_content, phrase):
    """No FAQ answer (EN or ES) may contain promising/miracle phrasing.

    These phrases overstate medical/cosmetic outcomes. They were absent
    from `bot_content.json` at the time of writing — this test guards
    against future copy edits that introduce them.
    """
    from bot.content_loader import get_faq_entries

    for entry in get_faq_entries():
        for field in ("answer_en", "answer_es", "answer"):
            text = (entry.get(field) or "").lower()
            if phrase in text:
                start = max(0, text.find(phrase) - 40)
                end = text.find(phrase) + len(phrase) + 40
                pytest.fail(
                    f"FAQ {entry.get('question')!r} {field} contains "
                    f"forbidden phrase {phrase!r}: ...{text[start:end]}..."
                )


# ─── End-to-end: rules reach the model ────────────────────────────────


def test_anti_hallucination_rules_reach_anthropic_system_prompt(
    real_content,
    monkeypatch,
):
    """The real business_context is actually passed to Claude on every call.

    Closes the gap between "rules exist in bot_content.json" and "rules
    reach the model": loads the real content, mocks Anthropic, and asserts
    the full constructed `system` payload contains both the
    no-hallucination rule and the redirect target.
    """
    from bot import ai_responder

    captured: dict = {}

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(content=[SimpleNamespace(text="canned reply")])

    class FakeClient:
        def __init__(self, **_kwargs):
            self.messages = FakeMessages()

    monkeypatch.setattr(ai_responder, "ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.setattr(ai_responder.anthropic, "Anthropic", FakeClient)

    ai_responder.get_ai_response("how much is blepharoplasty?")

    system = captured["system"].lower()
    assert "never guarantee" in system
    assert "invent" in system
    assert "tulumbotox.com/book" in system
