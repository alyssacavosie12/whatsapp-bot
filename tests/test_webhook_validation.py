"""Webhook payload validation: events.py, schema.py, http_hardening.py.

Three small modules that handle malformed/edge-case input from Meta and
optional dependencies (flask-talisman, flask-limiter, jsonschema).
Existing tests exercise the happy paths through /webhook end-to-end;
these unit tests fill in the type-rejection branches and the ImportError
fallbacks that the integration tests can't reach.
"""

from __future__ import annotations

import sys

from flask import Flask

# ─── webhook/events.py: malformed payload skipping ──────────────────


def test_events_skips_non_list_entry():
    from webhook.events import iter_webhook_messages

    assert list(iter_webhook_messages({"entry": "not a list"})) == []


def test_events_skips_non_dict_entry_items():
    from webhook.events import iter_webhook_messages

    assert list(iter_webhook_messages({"entry": ["string", None]})) == []


def test_events_skips_non_list_changes():
    from webhook.events import iter_webhook_messages

    assert list(iter_webhook_messages({"entry": [{"changes": "bad"}]})) == []


def test_events_skips_non_dict_change_items():
    from webhook.events import iter_webhook_messages

    assert list(iter_webhook_messages({"entry": [{"changes": [None, 42]}]})) == []


def test_events_skips_non_dict_value():
    from webhook.events import iter_webhook_messages

    payload = {"entry": [{"changes": [{"value": "bad"}]}]}
    assert list(iter_webhook_messages(payload)) == []


def test_events_skips_non_list_messages():
    from webhook.events import iter_webhook_messages

    payload = {"entry": [{"changes": [{"value": {"messages": "bad"}}]}]}
    assert list(iter_webhook_messages(payload)) == []


def test_events_skips_non_dict_message_items_but_yields_dicts():
    """Non-dict messages are skipped; valid dicts in the same list still come through."""
    from webhook.events import iter_webhook_messages

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                "bad",
                                None,
                                {"id": "wamid.1", "type": "text"},
                            ]
                        }
                    }
                ]
            }
        ]
    }
    yielded = list(iter_webhook_messages(payload))
    assert len(yielded) == 1
    assert yielded[0][1]["id"] == "wamid.1"


# ─── webhook/events.py: iter_webhook_calls ──────────────────────────


def test_call_events_skips_when_calls_missing():
    from webhook.events import iter_webhook_calls

    payload = {"entry": [{"changes": [{"value": {"messages": []}}]}]}
    assert list(iter_webhook_calls(payload)) == []


def test_call_events_skips_non_list_calls():
    from webhook.events import iter_webhook_calls

    payload = {"entry": [{"changes": [{"value": {"calls": "not-a-list"}}]}]}
    assert list(iter_webhook_calls(payload)) == []


def test_call_events_skips_non_dict_call_items_but_yields_dicts():
    """Non-dict call entries are skipped; valid dicts in the same list still come through."""
    from webhook.events import iter_webhook_calls

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "calls": [
                                "bad",
                                None,
                                {"id": "wacid.1", "from": "5219841050808", "status": "missed"},
                            ]
                        }
                    }
                ]
            }
        ]
    }
    yielded = list(iter_webhook_calls(payload))
    assert len(yielded) == 1
    assert yielded[0][1]["id"] == "wacid.1"
    assert yielded[0][1]["status"] == "missed"


def test_call_events_skips_non_dict_value():
    from webhook.events import iter_webhook_calls

    payload = {"entry": [{"changes": [{"value": "not-a-dict"}]}]}
    assert list(iter_webhook_calls(payload)) == []



# ─── webhook/schema.py: each error branch ───────────────────────────


def test_manual_schema_rejects_non_object_payload():
    from webhook.schema import _manual_validate_webhook_payload

    ok, err = _manual_validate_webhook_payload([])
    assert not ok
    assert "object" in err


def test_manual_schema_rejects_missing_or_empty_entry():
    from webhook.schema import _manual_validate_webhook_payload

    ok, err = _manual_validate_webhook_payload({"entry": []})
    assert not ok
    assert "entry" in err

    ok, err = _manual_validate_webhook_payload({"entry": "bad"})
    assert not ok


def test_manual_schema_rejects_non_object_entry_item():
    from webhook.schema import _manual_validate_webhook_payload

    ok, err = _manual_validate_webhook_payload({"entry": ["bad"]})
    assert not ok
    assert "entry items" in err


def test_manual_schema_rejects_missing_or_empty_changes():
    from webhook.schema import _manual_validate_webhook_payload

    ok, err = _manual_validate_webhook_payload({"entry": [{"changes": []}]})
    assert not ok
    assert "changes" in err


def test_manual_schema_rejects_non_object_change_item():
    from webhook.schema import _manual_validate_webhook_payload

    ok, err = _manual_validate_webhook_payload({"entry": [{"changes": ["bad"]}]})
    assert not ok
    assert "change items" in err


def test_manual_schema_rejects_non_object_value():
    from webhook.schema import _manual_validate_webhook_payload

    ok, err = _manual_validate_webhook_payload({"entry": [{"changes": [{"value": "bad"}]}]})
    assert not ok
    assert "value" in err


def test_manual_schema_rejects_non_list_messages():
    from webhook.schema import _manual_validate_webhook_payload

    ok, err = _manual_validate_webhook_payload(
        {"entry": [{"changes": [{"value": {"messages": "bad"}}]}]}
    )
    assert not ok
    assert "messages" in err


def test_manual_schema_rejects_non_object_message_item():
    from webhook.schema import _manual_validate_webhook_payload

    ok, err = _manual_validate_webhook_payload(
        {"entry": [{"changes": [{"value": {"messages": ["bad"]}}]}]}
    )
    assert not ok
    assert "message items" in err


def test_manual_schema_rejects_non_string_from():
    from webhook.schema import _manual_validate_webhook_payload

    ok, err = _manual_validate_webhook_payload(
        {"entry": [{"changes": [{"value": {"messages": [{"from": 123}]}}]}]}
    )
    assert not ok
    assert "message.from" in err


def test_manual_schema_rejects_non_string_type():
    from webhook.schema import _manual_validate_webhook_payload

    ok, err = _manual_validate_webhook_payload(
        {"entry": [{"changes": [{"value": {"messages": [{"type": 123}]}}]}]}
    )
    assert not ok
    assert "message.type" in err


def test_manual_schema_rejects_non_object_text_payload():
    from webhook.schema import _manual_validate_webhook_payload

    ok, err = _manual_validate_webhook_payload(
        {
            "entry": [
                {"changes": [{"value": {"messages": [{"type": "text", "text": "bad-not-object"}]}}]}
            ]
        }
    )
    assert not ok
    assert "text message" in err


def test_manual_schema_accepts_valid_payload():
    from webhook.schema import _manual_validate_webhook_payload

    ok, err = _manual_validate_webhook_payload(
        {
            "entry": [
                {
                    "changes": [
                        {"value": {"messages": [{"id": "wamid.1", "from": "100", "type": "text"}]}}
                    ]
                }
            ]
        }
    )
    assert ok
    assert err == ""


def test_validate_falls_back_to_manual_when_jsonschema_unavailable(monkeypatch):
    """If jsonschema isn't installed, the manual validator must still run."""
    monkeypatch.setitem(sys.modules, "jsonschema", None)

    from webhook.schema import validate_webhook_payload

    ok, err = validate_webhook_payload({"entry": []})
    assert not ok
    assert "entry" in err


# ─── webhook/http_hardening.py: optional-dep + empty-config branches ───


def test_configure_talisman_is_a_noop_when_flask_talisman_missing(monkeypatch):
    """Missing flask_talisman must log a warning and not crash."""
    monkeypatch.setitem(sys.modules, "flask_talisman", None)

    from webhook.http_hardening import configure_talisman

    app = Flask(__name__)
    # Should not raise; returns None.
    assert configure_talisman(app, force_https=False) is None


def test_build_webhook_rate_limit_is_passthrough_when_rate_limit_empty():
    """Empty rate_limit must return an identity decorator (no limiting)."""
    from webhook.http_hardening import build_webhook_rate_limit

    app = Flask(__name__)
    decorator = build_webhook_rate_limit(app, key_func=lambda: "x", rate_limit="", storage_uri="")

    def view():
        return "ok"

    assert decorator(view) is view


def test_build_webhook_rate_limit_is_passthrough_when_flask_limiter_missing(monkeypatch):
    """Missing flask_limiter must degrade to a passthrough, not crash."""
    monkeypatch.setitem(sys.modules, "flask_limiter", None)

    from webhook.http_hardening import build_webhook_rate_limit

    app = Flask(__name__)
    decorator = build_webhook_rate_limit(
        app, key_func=lambda: "x", rate_limit="100/min", storage_uri=""
    )

    def view():
        return "ok"

    assert decorator(view) is view
