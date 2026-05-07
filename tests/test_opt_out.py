"""Opt-out compliance tests: LFPDPPP Oposición / CCPA / WhatsApp Policy.

Four layers:
- Keyword detection in `bot.opt_out_keywords` (EN+ES, false-positive guards).
- Service-layer opt-out check fails-open on DB outage so a Postgres
  hiccup doesn't drop every reply.
- Router silences opted-out users (ZERO outbound) and short-circuits to
  recording + one confirmation when a fresh user sends STOP/BAJA.
- /admin/data-subject/delete endpoint enforces admin auth + CSRF and
  delegates to the inbox service for ARCO Cancelación.
"""

from __future__ import annotations

import base64

import pytest
from werkzeug.security import generate_password_hash

from tests.support import make_app_modules

PHONE = "37368826828"


# ─── Keyword detection (bot/opt_out_keywords.py) ──────────────────────


@pytest.mark.parametrize(
    "message",
    [
        "STOP",
        "stop",
        "Stop.",
        "stop!",
        "stop now",
        "UNSUBSCRIBE",
        "unsubscribe",
        "please unsubscribe",
        "OPT OUT",
        "opt-out",
        "remove me",
        "stop messages",
        "stop messaging",
        "leave me alone",
        "do not contact me",
        "no more messages",
        "DND",
    ],
)
def test_opt_out_detection_en(message: str) -> None:
    """Standard English opt-out keywords match."""
    from bot.opt_out_keywords import is_opt_out_request

    matched, keyword, lang = is_opt_out_request(message)
    assert matched, f"{message!r} should match"
    assert lang == "en"
    assert keyword


@pytest.mark.parametrize(
    "message",
    [
        "BAJA",
        "baja",
        "no molesten",
        "no molestar",
        "darme de baja",
        "darse de baja",
        "no escriban",
        "DETENER",
        "detener",
        "no contactar",
        "no quiero mensajes",
    ],
)
def test_opt_out_detection_es(message: str) -> None:
    """Standard Spanish opt-out keywords match."""
    from bot.opt_out_keywords import is_opt_out_request

    matched, _keyword, lang = is_opt_out_request(message)
    assert matched, f"{message!r} should match"
    assert lang == "es"


@pytest.mark.parametrize(
    "message",
    [
        "",
        "   ",
        "stop the rain please now",  # >2 tokens, no phrase match
        "soy alto y guapo",  # contains "alto" but >2 tokens
        "I want to cancel my appointment please",  # >2 tokens
        "hello how much is botox per unit?",  # benign
        "ya no quiero ese tratamiento si me dan otro",  # contains "ya no" (we dropped that one)
    ],
)
def test_opt_out_detection_does_not_fire_on_ambiguous_input(message: str) -> None:
    """Conservative single-word rule prevents false positives in long messages."""
    from bot.opt_out_keywords import is_opt_out_request

    matched, keyword, lang = is_opt_out_request(message)
    assert not matched, f"{message!r} should NOT match (got {keyword=}, {lang=})"


def test_opt_out_detection_skips_messages_longer_than_eight_tokens() -> None:
    """Phrase match is bounded so an essay containing 'stop messaging' doesn't trigger."""
    from bot.opt_out_keywords import is_opt_out_request

    long_message = "please stop messaging me thank you very much i hope you understand"
    matched, _kw, _lang = is_opt_out_request(long_message)
    assert not matched


def test_opt_out_detection_tolerates_punctuation_and_case() -> None:
    """STOP! and stop. and STOP both count."""
    from bot.opt_out_keywords import is_opt_out_request

    for variant in ("STOP", "stop.", "STOP!", "Stop"):
        matched, _kw, _lang = is_opt_out_request(variant)
        assert matched, f"{variant!r} must match"


# ─── Service layer (inbox/service.py) ─────────────────────────────────


def test_is_opted_out_returns_false_when_inbox_not_configured(monkeypatch):
    """Without INBOX_ENABLED + DATABASE_URL the check is a cheap no-op."""
    import inbox.service as service

    monkeypatch.setattr(service, "INBOX_ENABLED", False)
    monkeypatch.setattr(service, "INBOX_DATABASE_URL", "")

    assert service.is_opted_out(PHONE) is False


def test_is_opted_out_fails_open_on_database_error(monkeypatch):
    """A DB outage must not silence every customer — log and return False."""
    import inbox.service as service
    import inbox.store as store

    monkeypatch.setattr(service, "INBOX_ENABLED", True)
    monkeypatch.setattr(service, "INBOX_DATABASE_URL", "postgresql://x")

    def boom(*_args, **_kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(store, "is_opted_out", boom)

    assert service.is_opted_out(PHONE) is False


def test_record_opt_out_swallows_db_errors(monkeypatch, caplog):
    """A failing record must not break the webhook handler."""
    import inbox.service as service
    import inbox.store as store

    monkeypatch.setattr(service, "INBOX_ENABLED", True)
    monkeypatch.setattr(service, "INBOX_DATABASE_URL", "postgresql://x")
    monkeypatch.setattr(service, "INBOX_PROOF_SECRET", "s")
    monkeypatch.setattr(service, "INBOX_ENCRYPTION_KEY", "")

    def boom(*_args, **_kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(store, "record_opt_out", boom)

    result = service.record_opt_out(PHONE, source="whatsapp_keyword", keyword_used="stop")
    assert result is False


# ─── Router integration (bot/message_processor.py) ────────────────────


def _opt_out_payload(body: str, *, message_id: str, phone: str = PHONE) -> dict:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"profile": {"name": "Test"}}],
                            "messages": [
                                {
                                    "id": message_id,
                                    "from": phone,
                                    "type": "text",
                                    "text": {"body": body},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }


def _wire_router(app_module, monkeypatch):
    """Mock signature, rate-limit, and outbound for router-level integration tests."""
    monkeypatch.setattr(app_module, "verify_meta_signature", lambda: True)
    monkeypatch.setattr(app_module, "allow_phone_message", lambda _phone: True)


def test_opted_out_user_receives_zero_outbound(content_file, monkeypatch):
    """A user whose phone is in inbox_opt_outs must get NO reply, not even media/unknown."""
    import inbox.service as service

    app_module, flask_app = make_app_modules()
    _wire_router(app_module, monkeypatch)

    sent = []
    monkeypatch.setattr(
        app_module, "send_whatsapp_message", lambda to, text: sent.append((to, text))
    )
    monkeypatch.setattr(service, "is_opted_out", lambda _phone: True)

    client = flask_app.test_client()
    response = client.post("/webhook", json=_opt_out_payload("hello", message_id="wamid.silent.1"))

    # The webhook handler always returns 200 ok (background processing); the
    # opt-out evidence is the absence of outbound messages.
    assert response.status_code == 200
    assert sent == [], "Opted-out user must receive no outbound message"


def test_opted_out_user_does_not_trigger_faq_or_ai(content_file, monkeypatch):
    """Silenced users skip the FAQ matcher and AI fallback entirely."""
    import inbox.service as service

    app_module, flask_app = make_app_modules()
    _wire_router(app_module, monkeypatch)

    monkeypatch.setattr(app_module, "send_whatsapp_message", lambda to, text: None)
    monkeypatch.setattr(service, "is_opted_out", lambda _phone: True)

    faq_calls = []
    monkeypatch.setattr(app_module, "find_best_faq_match", lambda t: faq_calls.append(t) or "FAQ")

    ai_calls = []
    monkeypatch.setattr(
        app_module,
        "get_ai_response",
        lambda *args, **kwargs: ai_calls.append(args) or "ai",
    )

    client = flask_app.test_client()
    client.post("/webhook", json=_opt_out_payload("price", message_id="wamid.silent.2"))

    assert faq_calls == [], "FAQ matcher must not be called for opted-out users"
    assert ai_calls == [], "AI must not be called for opted-out users"


def test_stop_keyword_records_opt_out_and_sends_one_confirmation(content_file, monkeypatch):
    """A fresh STOP records opt-out via service and sends exactly one confirmation."""
    import inbox.service as service

    app_module, flask_app = make_app_modules()
    _wire_router(app_module, monkeypatch)

    sent = []
    monkeypatch.setattr(
        app_module, "send_whatsapp_message", lambda to, text: sent.append((to, text))
    )
    monkeypatch.setattr(service, "is_opted_out", lambda _phone: False)

    recorded = []

    def fake_record(phone, **kwargs):
        recorded.append((phone, kwargs))
        return True

    monkeypatch.setattr(service, "record_opt_out", fake_record)

    client = flask_app.test_client()
    response = client.post("/webhook", json=_opt_out_payload("STOP", message_id="wamid.opt.1"))

    # Webhook always returns 200 ok; side effects are the proof of opt-out.
    assert response.status_code == 200
    assert len(recorded) == 1
    assert recorded[0][0] == PHONE
    assert recorded[0][1]["source"] == "whatsapp_keyword"
    assert recorded[0][1]["keyword_used"] == "stop"
    assert recorded[0][1]["language"] == "en"
    assert len(sent) == 1, "Exactly one confirmation must be sent"


def test_stop_keyword_short_circuits_before_faq_and_ai(content_file, monkeypatch):
    """STOP must not run FAQ matching or AI fallback."""
    import inbox.service as service

    app_module, flask_app = make_app_modules()
    _wire_router(app_module, monkeypatch)

    monkeypatch.setattr(app_module, "send_whatsapp_message", lambda to, text: None)
    monkeypatch.setattr(service, "is_opted_out", lambda _phone: False)
    monkeypatch.setattr(service, "record_opt_out", lambda *a, **kw: True)

    faq_calls = []
    monkeypatch.setattr(app_module, "find_best_faq_match", lambda t: faq_calls.append(t) or None)

    ai_calls = []
    monkeypatch.setattr(
        app_module,
        "get_ai_response",
        lambda *args, **kwargs: ai_calls.append(args) or "ai",
    )

    client = flask_app.test_client()
    client.post("/webhook", json=_opt_out_payload("STOP", message_id="wamid.opt.2"))

    assert faq_calls == [], "STOP must short-circuit before FAQ"
    assert ai_calls == [], "STOP must short-circuit before AI"


def test_baja_records_opt_out_in_spanish(content_file, monkeypatch):
    """The Spanish keyword BAJA records the opt-out as language=es."""
    import inbox.service as service

    app_module, flask_app = make_app_modules()
    _wire_router(app_module, monkeypatch)

    sent = []
    monkeypatch.setattr(
        app_module, "send_whatsapp_message", lambda to, text: sent.append((to, text))
    )
    monkeypatch.setattr(service, "is_opted_out", lambda _phone: False)

    recorded = []

    def fake_record(phone, **kwargs):
        recorded.append(kwargs)
        return True

    monkeypatch.setattr(service, "record_opt_out", fake_record)

    client = flask_app.test_client()
    response = client.post("/webhook", json=_opt_out_payload("BAJA", message_id="wamid.opt.3"))

    assert response.status_code == 200
    assert recorded[0]["language"] == "es"
    confirmation = sent[0][1].lower()
    assert (
        "cancelado" in confirmation
        or "suscripcion" in confirmation
        or "suscripción" in confirmation
    )


# ─── ARCO endpoint (inbox/routes.py) ───────────────────────────────────


def _basic_auth(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _configure_admin(app_module, monkeypatch):
    monkeypatch.setattr(app_module, "INBOX_ENABLED", True)
    monkeypatch.setattr(app_module, "INBOX_DATABASE_URL", "postgresql://x")
    monkeypatch.setattr(app_module, "INBOX_ENCRYPTION_KEY", "configured-key")
    monkeypatch.setattr(app_module, "INBOX_ADMIN_USERNAME", "owner")
    monkeypatch.setattr(
        app_module,
        "INBOX_ADMIN_PASSWORD_HASH",
        generate_password_hash("secret"),
    )
    monkeypatch.setattr(app_module, "INBOX_VIEWER_USERNAME", "viewer")
    monkeypatch.setattr(
        app_module,
        "INBOX_VIEWER_PASSWORD_HASH",
        generate_password_hash("view"),
    )
    monkeypatch.setattr(app_module, "META_APP_SECRET", "csrf-secret")


def test_arco_endpoint_rejects_viewer_role(content_file, monkeypatch):
    """Viewer role cannot trigger ARCO deletion (admin-only)."""
    app_module, flask_app = make_app_modules()
    _configure_admin(app_module, monkeypatch)

    client = flask_app.test_client()
    response = client.post(
        "/admin/data-subject/delete",
        data={"phone": PHONE},
        headers=_basic_auth("viewer", "view"),
    )

    assert response.status_code == 403


def test_arco_endpoint_requires_csrf_token(content_file, monkeypatch):
    """Without a valid CSRF token the endpoint refuses (forged-form defense)."""
    app_module, flask_app = make_app_modules()
    _configure_admin(app_module, monkeypatch)

    client = flask_app.test_client()
    response = client.post(
        "/admin/data-subject/delete",
        data={"phone": PHONE},
        headers=_basic_auth("owner", "secret"),
    )

    assert response.status_code == 403


def test_arco_endpoint_validates_phone(content_file, monkeypatch):
    """Empty or non-E.164 phone returns 400 and never calls the deletion service."""
    import inbox.service as service

    app_module, flask_app = make_app_modules()
    _configure_admin(app_module, monkeypatch)

    deletes = []
    monkeypatch.setattr(
        service,
        "delete_user_data",
        lambda phone, delete_opt_out_record: deletes.append((phone, delete_opt_out_record)),
    )

    token = app_module.inbox_csrf_token("owner", "arco_delete", 0)
    client = flask_app.test_client()

    empty = client.post(
        "/admin/data-subject/delete",
        data={"phone": "", "csrf_token": token},
        headers=_basic_auth("owner", "secret"),
    )
    invalid = client.post(
        "/admin/data-subject/delete",
        data={"phone": "https://attacker.invalid", "csrf_token": token},
        headers=_basic_auth("owner", "secret"),
    )

    assert empty.status_code == 400
    assert invalid.status_code == 400
    assert deletes == [], "delete_user_data must not run for invalid input"


def test_arco_endpoint_deletes_data_and_audits(content_file, monkeypatch):
    """Happy path: returns counts, calls delete service, writes audit event."""
    import inbox.service as service

    app_module, flask_app = make_app_modules()
    _configure_admin(app_module, monkeypatch)

    deletes = []

    def fake_delete(phone, *, delete_opt_out_record):
        deletes.append((phone, delete_opt_out_record))
        return {"messages": 3, "opt_in_proofs": 1, "opt_outs": 0}

    monkeypatch.setattr(service, "delete_user_data", fake_delete)

    audits = []
    monkeypatch.setattr(app_module, "record_audit_event", lambda *a, **kw: audits.append(kw))

    token = app_module.inbox_csrf_token("owner", "arco_delete", 0)
    client = flask_app.test_client()
    response = client.post(
        "/admin/data-subject/delete",
        data={"phone": PHONE, "csrf_token": token},
        headers=_basic_auth("owner", "secret"),
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["deleted"] == {"messages": 3, "opt_in_proofs": 1, "opt_outs": 0}
    assert deletes == [(PHONE, False)], "default keeps the opt-out record"
    assert audits[0]["action"] == "arco_cancelacion"
    assert audits[0]["metadata"]["delete_opt_out_record"] is False


def test_arco_endpoint_can_delete_opt_out_record_when_requested(content_file, monkeypatch):
    """Passing delete_opt_out_record=true also drops the opt-out evidence row."""
    import inbox.service as service

    app_module, flask_app = make_app_modules()
    _configure_admin(app_module, monkeypatch)

    deletes = []

    def fake_delete(phone, *, delete_opt_out_record):
        deletes.append((phone, delete_opt_out_record))
        return {"messages": 0, "opt_in_proofs": 0, "opt_outs": 1}

    monkeypatch.setattr(service, "delete_user_data", fake_delete)
    monkeypatch.setattr(app_module, "record_audit_event", lambda *a, **kw: None)

    token = app_module.inbox_csrf_token("owner", "arco_delete", 0)
    client = flask_app.test_client()
    response = client.post(
        "/admin/data-subject/delete",
        data={"phone": PHONE, "csrf_token": token, "delete_opt_out_record": "true"},
        headers=_basic_auth("owner", "secret"),
    )

    assert response.status_code == 200
    assert deletes == [(PHONE, True)]


# ─── BSUID readiness ────────────────────────────────────────────────────


def test_bsuid_sender_is_not_rejected_as_invalid(content_file, monkeypatch):
    """Webhook with a BSUID `from` (post June 2026) must not be dropped."""
    import inbox.service as service

    app_module, flask_app = make_app_modules()
    _wire_router(app_module, monkeypatch)

    sent = []
    monkeypatch.setattr(
        app_module, "send_whatsapp_message", lambda to, text: sent.append((to, text))
    )
    monkeypatch.setattr(service, "is_opted_out", lambda _id: False)

    bsuid = "user_2026.0001:meta"
    payload = _opt_out_payload("hi", message_id="wamid.bsuid.1", phone=bsuid)

    client = flask_app.test_client()
    response = client.post("/webhook", json=payload)

    assert response.status_code == 200
    # BSUID-addressed reply goes out unchanged (not normalized as phone).
    assert sent and sent[0][0] == bsuid


def test_bsuid_stop_keyword_records_opt_out_with_bsuid_type(content_file, monkeypatch):
    """STOP from a BSUID sender records opt-out tagged sender_external_id_type='bsuid'."""
    import inbox.service as service

    app_module, flask_app = make_app_modules()
    _wire_router(app_module, monkeypatch)

    monkeypatch.setattr(app_module, "send_whatsapp_message", lambda to, text: None)
    monkeypatch.setattr(service, "is_opted_out", lambda _id: False)

    recorded = []

    def fake_record(sender, **kwargs):
        recorded.append((sender, kwargs))
        return True

    monkeypatch.setattr(service, "record_opt_out", fake_record)

    bsuid = "user_2026.bsuid.opt:meta"
    payload = _opt_out_payload("STOP", message_id="wamid.bsuid.opt.1", phone=bsuid)

    client = flask_app.test_client()
    client.post("/webhook", json=payload)

    assert len(recorded) == 1
    assert recorded[0][0] == bsuid
    assert recorded[0][1]["sender_external_id_type"] == "bsuid"


def test_arco_endpoint_accepts_bsuid_via_external_id_field(content_file, monkeypatch):
    """ARCO Cancelación works for BSUID subjects too, not only E.164 phones."""
    import inbox.service as service

    app_module, flask_app = make_app_modules()
    _configure_admin(app_module, monkeypatch)

    deletes = []

    def fake_delete(sender_id, *, delete_opt_out_record):
        deletes.append((sender_id, delete_opt_out_record))
        return {"messages": 0, "opt_in_proofs": 0, "opt_outs": 1}

    monkeypatch.setattr(service, "delete_user_data", fake_delete)
    monkeypatch.setattr(app_module, "record_audit_event", lambda *a, **kw: None)

    token = app_module.inbox_csrf_token("owner", "arco_delete", 0)
    client = flask_app.test_client()

    bsuid = "user_2026.arco:meta"
    response = client.post(
        "/admin/data-subject/delete",
        data={"external_id": bsuid, "csrf_token": token, "delete_opt_out_record": "true"},
        headers=_basic_auth("owner", "secret"),
    )

    assert response.status_code == 200
    assert deletes == [(bsuid, True)]
