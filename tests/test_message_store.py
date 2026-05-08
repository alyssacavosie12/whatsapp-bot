"""Unit tests for inbox/store.py with mocked psycopg.

The real Postgres-backed inbox runs against Railway's database. CI doesn't
have a Postgres; rather than reach for testcontainers, this module fakes
out the `psycopg` import via `_psycopg_modules` and asserts that the
right SQL and parameters are sent. Helper functions that don't touch the
DB (`_sha256`, `_fernet`, encryption round-trips) are tested directly.
"""

from __future__ import annotations

import sys

import pytest

# ─── Helper functions (no DB needed) ───────────────────────────────────


def test_database_key_is_stable_sha256():
    from inbox.store import _database_key

    assert _database_key("postgresql://x") == _database_key("postgresql://x")
    assert _database_key("a") != _database_key("b")
    assert len(_database_key("a")) == 64  # sha256 hex digest


def test_auto_migrate_default_true(monkeypatch):
    from inbox.store import _auto_migrate_enabled

    monkeypatch.delenv("INBOX_AUTO_MIGRATE", raising=False)
    assert _auto_migrate_enabled() is True


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1", True),
        ("true", True),
        ("yes", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("no", False),
        ("off", False),
        ("", False),
    ],
)
def test_auto_migrate_parses_env_truthy_strings(monkeypatch, value, expected):
    from inbox.store import _auto_migrate_enabled

    monkeypatch.setenv("INBOX_AUTO_MIGRATE", value)
    assert _auto_migrate_enabled() is expected


def test_sha256_empty_string_returns_empty():
    from inbox.store import _sha256

    assert _sha256("") == ""
    assert len(_sha256("hello")) == 64


def test_fernet_returns_none_when_no_key():
    from inbox.store import _fernet

    assert _fernet("") is None


def test_fernet_returns_cipher_when_key_valid():
    from cryptography.fernet import Fernet

    from inbox.store import _fernet

    key = Fernet.generate_key().decode("utf-8")
    cipher = _fernet(key)

    assert cipher is not None
    encrypted = cipher.encrypt(b"hello")
    assert cipher.decrypt(encrypted) == b"hello"


def test_fernet_raises_for_invalid_key():
    from inbox.store import MessageStoreUnavailable, _fernet

    with pytest.raises(MessageStoreUnavailable, match="invalid"):
        _fernet("not-a-valid-fernet-key")


def test_prepare_body_without_encryption_returns_plaintext():
    from inbox.store import _prepare_body

    text, encrypted, length, digest = _prepare_body("hello", encryption_key="")

    assert text == "hello"
    assert encrypted is False
    assert length == 5
    assert len(digest) == 64


def test_prepare_body_with_encryption_returns_ciphertext():
    from cryptography.fernet import Fernet

    from inbox.store import _prepare_body

    key = Fernet.generate_key().decode("utf-8")
    text, encrypted, length, digest = _prepare_body("hello", encryption_key=key)

    assert encrypted is True
    assert text != "hello"  # ciphertext, not plaintext
    assert length == 5  # length is of the *plaintext*
    assert len(digest) == 64


def test_prepare_sensitive_field_skips_encryption_when_empty():
    from cryptography.fernet import Fernet

    from inbox.store import _prepare_sensitive_field

    key = Fernet.generate_key().decode("utf-8")
    value, encrypted, digest = _prepare_sensitive_field("", 32, encryption_key=key)

    # Empty values stay empty even with encryption configured.
    assert value == ""
    assert encrypted is False
    assert digest == ""


def test_read_body_returns_plaintext_when_not_encrypted():
    from inbox.store import _read_body

    assert _read_body("hello", encrypted=False, encryption_key="") == "hello"


def test_read_body_returns_marker_when_key_missing():
    from inbox.store import _read_body

    result = _read_body("ciphertext", encrypted=True, encryption_key="")

    assert "encrypted" in result.lower()
    assert "INBOX_ENCRYPTION_KEY" in result


def test_read_body_round_trips_with_correct_key():
    from cryptography.fernet import Fernet

    from inbox.store import _prepare_body, _read_body

    key = Fernet.generate_key().decode("utf-8")
    ciphertext, _enc, _len, _digest = _prepare_body("secret", encryption_key=key)

    assert _read_body(ciphertext, encrypted=True, encryption_key=key) == "secret"


def test_read_body_returns_decrypt_failed_marker_on_bad_ciphertext():
    from cryptography.fernet import Fernet

    from inbox.store import _read_body

    key = Fernet.generate_key().decode("utf-8")

    result = _read_body("garbage", encrypted=True, encryption_key=key)

    assert "decrypt failed" in result


def test_read_sensitive_field_falls_back_to_fallback_when_no_key():
    from inbox.store import _read_sensitive_field

    assert (
        _read_sensitive_field(
            "ciphertext",
            encrypted=True,
            encryption_key="",
            fallback="MASKED",
        )
        == "MASKED"
    )


def test_read_sensitive_field_falls_back_on_decrypt_failure():
    from cryptography.fernet import Fernet

    from inbox.store import _read_sensitive_field

    key = Fernet.generate_key().decode("utf-8")
    assert (
        _read_sensitive_field(
            "garbage",
            encrypted=True,
            encryption_key=key,
            fallback="FALLBACK",
        )
        == "FALLBACK"
    )


def test_connect_raises_when_database_url_missing():
    from inbox.store import MessageStoreUnavailable, _connect

    with pytest.raises(MessageStoreUnavailable, match="DATABASE_URL"):
        _connect("")


def test_psycopg_modules_raises_when_psycopg_unavailable(monkeypatch):
    """If psycopg isn't installed, store usage must fail loudly, not silently."""
    monkeypatch.setitem(sys.modules, "psycopg", None)

    import importlib

    import inbox.store as store

    importlib.reload(store)

    with pytest.raises(store.MessageStoreUnavailable, match="psycopg"):
        store._psycopg_modules()


# ─── Fake psycopg fixture for DB-touching functions ───────────────────


class _FakeCursor:
    def __init__(self):
        self.executed: list[tuple[str, object]] = []
        self.rowcount = 0
        self._fetchall_result: list[dict] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self._fetchall_result


class _FakeConn:
    def __init__(self):
        self._cursor = _FakeCursor()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self._cursor


@pytest.fixture
def fake_db(monkeypatch):
    """Wire `inbox.store` to an in-memory fake psycopg.

    Returns the fake connection so tests can inspect the SQL + params that
    were executed, and stage rows for SELECTs that follow.
    """
    import inbox.store as store

    fake_conn = _FakeConn()

    class FakePsycopg:
        @staticmethod
        def connect(_url, **_kwargs):
            return fake_conn

    def fake_jsonb(value):
        return ("__JSONB__", value)

    fake_dict_row = object()

    monkeypatch.setattr(
        store,
        "_psycopg_modules",
        lambda: (FakePsycopg, fake_dict_row, fake_jsonb),
    )
    monkeypatch.setattr(store, "_connect", lambda *_args, **_kwargs: fake_conn)

    # Don't let _SCHEMA_READY persist between tests.
    store._SCHEMA_READY.clear()

    return fake_conn


# ─── ensure_schema ────────────────────────────────────────────────────


def test_ensure_schema_creates_tables_on_first_call(fake_db):
    from inbox.store import ensure_schema

    ensure_schema("postgresql://x")

    sqls = " ".join(sql for sql, _params in fake_db._cursor.executed)
    assert "CREATE TABLE IF NOT EXISTS inbox_messages" in sqls
    assert "CREATE TABLE IF NOT EXISTS inbox_audit_events" in sqls
    assert "CREATE TABLE IF NOT EXISTS inbox_opt_in_proofs" in sqls


def test_ensure_schema_is_idempotent(fake_db):
    from inbox.store import ensure_schema

    ensure_schema("postgresql://x")
    first_count = len(fake_db._cursor.executed)
    ensure_schema("postgresql://x")
    # Second call must short-circuit on the per-URL cache.
    assert len(fake_db._cursor.executed) == first_count


def test_ensure_schema_skips_when_auto_migrate_disabled(fake_db, monkeypatch):
    from inbox.store import ensure_schema

    monkeypatch.setenv("INBOX_AUTO_MIGRATE", "false")
    ensure_schema("postgresql://x")

    # No SQL should run when migrations are turned off.
    assert fake_db._cursor.executed == []


# ─── cleanup_expired_messages ─────────────────────────────────────────


def test_cleanup_expired_messages_zero_retention_is_noop(fake_db):
    from inbox.store import cleanup_expired_messages

    deleted = cleanup_expired_messages("postgresql://x", retention_days=0)

    assert deleted == 0
    assert fake_db._cursor.executed == []


def test_cleanup_expired_messages_runs_three_deletes(fake_db):
    from inbox.store import cleanup_expired_messages

    fake_db._cursor.rowcount = 5
    cleanup_expired_messages("postgresql://x", retention_days=14)

    deletes = [sql for sql, _params in fake_db._cursor.executed if "DELETE FROM" in sql]
    assert len(deletes) == 3  # messages + audit + opt-in proofs


# ─── record_incoming_message ──────────────────────────────────────────


def test_record_incoming_message_inserts_with_sanitized_params(fake_db):
    from inbox.store import record_incoming_message

    record_incoming_message(
        "postgresql://x",
        whatsapp_message_id="wamid.1",
        sender_phone="37368826828",
        sender_phone_masked="***6828",
        sender_name="Test User",
        message_type="text",
        body="hello",
    )

    inserts = [
        (sql, params)
        for sql, params in fake_db._cursor.executed
        if "INSERT INTO inbox_messages" in sql
    ]
    assert len(inserts) == 1
    _sql, params = inserts[0]
    # Param order matches the INSERT VALUES (...) tuple.
    assert params[0] == "wamid.1"
    assert params[1] == "37368826828"
    assert params[2] == "***6828"
    assert params[5] == "Test User"  # stored_sender_name with no encryption
    assert params[8] == "text"
    assert params[9] == "hello"  # body, not encrypted
    assert params[10] is False  # body_encrypted flag
    assert params[11] == 5  # body_length


# ─── record_opt_in_proof ──────────────────────────────────────────────


def test_record_opt_in_proof_requires_proof_secret(fake_db):
    from inbox.store import MessageStoreUnavailable, record_opt_in_proof

    with pytest.raises(MessageStoreUnavailable, match="INBOX_PROOF_SECRET"):
        record_opt_in_proof(
            "postgresql://x",
            whatsapp_message_id="wamid.1",
            sender_phone="100",
            evidence={"a": 1},
            proof_secret="",
        )


def test_record_opt_in_proof_inserts_hmac(fake_db):
    from inbox.store import record_opt_in_proof

    record_opt_in_proof(
        "postgresql://x",
        whatsapp_message_id="wamid.1",
        sender_phone="100",
        evidence={"a": 1},
        proof_secret="shhhh",
    )

    inserts = [
        (sql, params)
        for sql, params in fake_db._cursor.executed
        if "INSERT INTO inbox_opt_in_proofs" in sql
    ]
    assert len(inserts) == 1
    _sql, params = inserts[0]
    proof_hmac = params[-1]
    assert isinstance(proof_hmac, str) and len(proof_hmac) == 64  # sha256 hex


def test_record_opt_in_proof_accepts_string_evidence(fake_db):
    """Pre-serialized string evidence must be passed through unchanged."""
    from inbox.store import record_opt_in_proof

    record_opt_in_proof(
        "postgresql://x",
        whatsapp_message_id="wamid.1",
        sender_phone="100",
        evidence="already-serialized",
        proof_secret="shhhh",
    )

    # Just verifying it didn't raise on a non-dict evidence input.
    inserts = [s for s, _ in fake_db._cursor.executed if "INSERT INTO inbox_opt_in_proofs" in s]
    assert len(inserts) == 1


# ─── first-contact lookup ─────────────────────────────────────────────


def test_has_incoming_message_for_sender_uses_sender_hash(fake_db):
    from inbox.store import _sha256, has_incoming_message_for_sender

    fake_db._cursor._fetchall_result = [{"exists": 1}]

    assert has_incoming_message_for_sender("postgresql://x", "37368826828") is True

    selects = [sql for sql, _params in fake_db._cursor.executed if "SELECT 1" in sql]
    assert selects
    _sql, params = fake_db._cursor.executed[-1]
    assert params == (_sha256("37368826828"),)


def test_has_incoming_message_for_sender_returns_false_without_rows(fake_db):
    from inbox.store import has_incoming_message_for_sender

    fake_db._cursor._fetchall_result = []

    assert has_incoming_message_for_sender("postgresql://x", "37368826828") is False


# ─── list_messages ────────────────────────────────────────────────────


def _row(**overrides):
    base = {
        "id": 1,
        "whatsapp_message_id": "wamid.1",
        "direction": "incoming",
        "sender_phone": "100",
        "sender_phone_masked": "***100",
        "sender_phone_encrypted": False,
        "sender_name": "Test",
        "sender_name_encrypted": False,
        "message_type": "text",
        "body": "hello",
        "body_encrypted": False,
        "body_length": 5,
        "created_at": __import__("datetime").datetime(2026, 5, 7),
        "deleted_at": None,
        "deleted_by": "",
    }
    base.update(overrides)
    return base


def test_list_messages_no_query_returns_inbox_messages(fake_db):
    from inbox.store import InboxMessage, list_messages

    fake_db._cursor._fetchall_result = [_row(), _row(id=2)]

    messages = list_messages("postgresql://x")

    assert len(messages) == 2
    assert all(isinstance(m, InboxMessage) for m in messages)
    sqls = [sql for sql, _p in fake_db._cursor.executed]
    selects = [s for s in sqls if "SELECT" in s]
    assert any("WHERE deleted_at IS NULL" in s for s in selects)


def test_list_messages_with_query_uses_search_branch(fake_db):
    from inbox.store import list_messages

    fake_db._cursor._fetchall_result = []
    list_messages("postgresql://x", query="alice")

    selects = [sql for sql, _p in fake_db._cursor.executed if "SELECT" in sql]
    assert any("ILIKE" in s for s in selects)


def test_list_messages_with_query_and_include_deleted(fake_db):
    from inbox.store import list_messages

    fake_db._cursor._fetchall_result = []
    list_messages("postgresql://x", query="alice", include_deleted=True)

    selects = [sql for sql, _p in fake_db._cursor.executed if "SELECT" in sql]
    assert selects, "must run a SELECT"
    # include_deleted means no WHERE deleted_at IS NULL filter.
    assert all("deleted_at IS NULL" not in s for s in selects)


def test_list_messages_include_deleted_no_query(fake_db):
    from inbox.store import list_messages

    fake_db._cursor._fetchall_result = []
    list_messages("postgresql://x", include_deleted=True)

    selects = [s for s, _ in fake_db._cursor.executed if "SELECT" in s]
    assert selects
    # No WHERE filter on deleted, no ILIKE search.
    assert all("ILIKE" not in s for s in selects)


# ─── soft_delete_message ──────────────────────────────────────────────


def test_soft_delete_message_runs_update_and_returns_rowcount(fake_db):
    from inbox.store import soft_delete_message

    fake_db._cursor.rowcount = 1

    deleted = soft_delete_message("postgresql://x", message_id=42, deleted_by="owner")

    assert deleted is True
    updates = [
        (sql, params) for sql, params in fake_db._cursor.executed if "UPDATE inbox_messages" in sql
    ]
    assert len(updates) == 1
    _sql, params = updates[0]
    assert params[0] == "owner"
    assert params[1] == 42


def test_soft_delete_message_returns_false_when_nothing_deleted(fake_db):
    from inbox.store import soft_delete_message

    fake_db._cursor.rowcount = 0

    assert soft_delete_message("postgresql://x", message_id=999, deleted_by="owner") is False


# ─── record_audit_event ───────────────────────────────────────────────


def test_record_audit_event_inserts_with_jsonb_metadata(fake_db):
    from inbox.store import record_audit_event

    record_audit_event(
        "postgresql://x",
        actor="owner",
        actor_role="admin",
        action="view_messages",
        target_message_id=42,
        ip_address="1.2.3.4",
        user_agent="curl/8",
        metadata={"result_count": 5},
    )

    inserts = [
        (sql, params)
        for sql, params in fake_db._cursor.executed
        if "INSERT INTO inbox_audit_events" in sql
    ]
    assert len(inserts) == 1
    _sql, params = inserts[0]
    assert params[0] == "owner"
    assert params[1] == "admin"
    assert params[2] == "view_messages"
    assert params[3] == 42
    # The fake Jsonb wraps the dict in a tuple marker.
    assert params[6] == ("__JSONB__", {"result_count": 5})


def test_record_audit_event_handles_no_metadata(fake_db):
    from inbox.store import record_audit_event

    record_audit_event(
        "postgresql://x",
        actor="owner",
        actor_role="admin",
        action="view_messages",
    )

    inserts = [
        (sql, params)
        for sql, params in fake_db._cursor.executed
        if "INSERT INTO inbox_audit_events" in sql
    ]
    _sql, params = inserts[0]
    assert params[6] == ("__JSONB__", {})  # default empty dict
