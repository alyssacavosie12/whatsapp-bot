"""Failed-login throttle for the admin inbox.

Mirrors the structure of tests/test_rate_limiting.py: unit tests for each
backend (`_AllowAllAuthThrottle`, `_LocalAuthThrottle`, `_RedisAuthThrottle`)
plus the public helpers (`inbox_auth_keys`, `is_inbox_auth_limited`,
`record_inbox_auth_failure`, `clear_inbox_auth_failures`).

Existing inbox tests in tests/test_inbox.py exercise the throttle through
the /admin/messages route (HTTP 429 on rate limit) but mock out the
backend; this file covers the backend implementations themselves.
"""

from __future__ import annotations

import sys
import time

# ─── _AllowAllAuthThrottle ────────────────────────────────────────────


def test_allow_all_throttle_never_limits_or_records():
    from inbox.auth_throttle import _AllowAllAuthThrottle

    backend = _AllowAllAuthThrottle()

    assert backend.is_limited("any-key") is False
    assert backend.record_failure("any-key") is False
    assert backend.clear("any-key") is None


# ─── _LocalAuthThrottle ───────────────────────────────────────────────


def test_local_throttle_allows_until_threshold_then_limits():
    from inbox.auth_throttle import _LocalAuthThrottle

    throttle = _LocalAuthThrottle(max_failures=3, window_seconds=60)

    # First two failures: not yet limited.
    assert throttle.record_failure("key") is False
    assert throttle.record_failure("key") is False
    # Third failure crosses the threshold.
    assert throttle.record_failure("key") is True
    assert throttle.is_limited("key") is True


def test_local_throttle_empty_key_is_inert():
    from inbox.auth_throttle import _LocalAuthThrottle

    throttle = _LocalAuthThrottle(max_failures=3, window_seconds=60)

    assert throttle.is_limited("") is False
    assert throttle.record_failure("") is False
    # Clear on empty key is also a no-op.
    throttle.clear("")


def test_local_throttle_clear_resets_counter():
    from inbox.auth_throttle import _LocalAuthThrottle

    throttle = _LocalAuthThrottle(max_failures=2, window_seconds=60)

    throttle.record_failure("key")
    throttle.record_failure("key")
    assert throttle.is_limited("key") is True

    throttle.clear("key")
    assert throttle.is_limited("key") is False


def test_local_throttle_resets_counter_when_window_rolls_over(monkeypatch):
    from inbox.auth_throttle import _LocalAuthThrottle

    throttle = _LocalAuthThrottle(max_failures=2, window_seconds=60)
    base = 1_000_000.0
    monkeypatch.setattr(time, "time", lambda: base)

    throttle.record_failure("key")
    throttle.record_failure("key")
    assert throttle.is_limited("key") is True

    monkeypatch.setattr(time, "time", lambda: base + 60)
    # New window: stale state evicted, no longer limited.
    assert throttle.is_limited("key") is False


def test_local_throttle_evicts_old_bucket_keys(monkeypatch):
    """Keys recorded in old buckets must not stay in the dict forever."""
    from inbox.auth_throttle import _LocalAuthThrottle

    throttle = _LocalAuthThrottle(max_failures=5, window_seconds=10)

    monkeypatch.setattr(time, "time", lambda: 1_000_000.0)
    throttle.record_failure("old-key")

    monkeypatch.setattr(time, "time", lambda: 1_000_020.0)  # two windows later
    throttle.record_failure("new-key")

    assert "old-key" not in throttle._failures
    assert "new-key" in throttle._failures


# ─── _RedisAuthThrottle ───────────────────────────────────────────────


def _install_fake_redis(monkeypatch, fake_client):
    class FakeRedisModule:
        class Redis:
            @staticmethod
            def from_url(_url, **_kwargs):
                return fake_client

    monkeypatch.setitem(sys.modules, "redis", FakeRedisModule)


def test_redis_throttle_records_failure_with_incr_and_first_expire(monkeypatch):
    """First failure in a bucket must INCR and EXPIRE so the key actually times out."""
    from inbox.auth_throttle import _RedisAuthThrottle

    calls = []

    class FakeRedis:
        counter = 0

        def incr(self, key):
            calls.append(("incr", key))
            FakeRedis.counter += 1
            return FakeRedis.counter

        def expire(self, key, seconds):
            calls.append(("expire", key, seconds))

        def get(self, _key):
            return str(FakeRedis.counter).encode("utf-8")

        def delete(self, _key):
            calls.append(("delete",))

    _install_fake_redis(monkeypatch, FakeRedis())
    throttle = _RedisAuthThrottle("redis://example", max_failures=2, window_seconds=42)

    assert throttle.record_failure("key") is False  # count=1, EXPIRE set
    assert throttle.record_failure("key") is True  # count=2 ≥ max
    assert throttle.is_limited("key") is True

    expire_calls = [c for c in calls if c[0] == "expire"]
    assert len(expire_calls) == 1, "EXPIRE must be set exactly once per bucket"
    assert expire_calls[0][2] == 42


def test_redis_throttle_is_limited_returns_false_when_no_record(monkeypatch):
    """A key with no recorded failures (`get` returns None) is not limited."""
    from inbox.auth_throttle import _RedisAuthThrottle

    class FakeRedis:
        def get(self, _key):
            return None

        def incr(self, _key):
            return 1

        def expire(self, *_args):
            pass

        def delete(self, *_args):
            pass

    _install_fake_redis(monkeypatch, FakeRedis())
    throttle = _RedisAuthThrottle("redis://example", max_failures=3, window_seconds=60)

    assert throttle.is_limited("never-failed") is False


def test_redis_throttle_fails_open_on_redis_error_in_is_limited(monkeypatch):
    """A Redis outage must allow the auth attempt — log and return not-limited."""
    from inbox.auth_throttle import _RedisAuthThrottle

    class FakeRedis:
        def get(self, _key):
            raise RuntimeError("connection refused")

        def incr(self, _key):
            raise RuntimeError("connection refused")

        def expire(self, *_args):
            pass

        def delete(self, *_args):
            raise RuntimeError("connection refused")

    _install_fake_redis(monkeypatch, FakeRedis())
    throttle = _RedisAuthThrottle("redis://example", max_failures=1, window_seconds=60)

    assert throttle.is_limited("key") is False
    assert throttle.record_failure("key") is False
    # Clear must also not raise even when Redis is down.
    throttle.clear("key")


def test_redis_throttle_clear_calls_delete(monkeypatch):
    from inbox.auth_throttle import _RedisAuthThrottle

    calls = []

    class FakeRedis:
        def get(self, _key):
            return None

        def incr(self, _key):
            return 1

        def expire(self, *_args):
            pass

        def delete(self, key):
            calls.append(key)

    _install_fake_redis(monkeypatch, FakeRedis())
    throttle = _RedisAuthThrottle("redis://example", max_failures=3, window_seconds=60)

    throttle.clear("the-key")

    assert calls and calls[0].endswith("the-key")


def test_redis_throttle_empty_key_is_inert(monkeypatch):
    from inbox.auth_throttle import _RedisAuthThrottle

    class FakeRedis:
        def get(self, _key):
            raise AssertionError("get must not be called for empty key")

        def incr(self, _key):
            raise AssertionError("incr must not be called for empty key")

        def expire(self, *_args):
            pass

        def delete(self, *_args):
            raise AssertionError("delete must not be called for empty key")

    _install_fake_redis(monkeypatch, FakeRedis())
    throttle = _RedisAuthThrottle("redis://example", max_failures=3, window_seconds=60)

    assert throttle.is_limited("") is False
    assert throttle.record_failure("") is False
    throttle.clear("")


# ─── _build_backend selection logic ───────────────────────────────────


def test_build_backend_returns_allow_all_when_max_failures_zero(monkeypatch):
    import inbox.auth_throttle as m

    monkeypatch.setattr(m, "INBOX_AUTH_MAX_FAILED_ATTEMPTS", 0)

    backend = m._build_backend()

    assert isinstance(backend, m._AllowAllAuthThrottle)


def test_build_backend_falls_back_to_local_when_redis_init_fails(monkeypatch):
    import inbox.auth_throttle as m

    monkeypatch.setattr(m, "INBOX_AUTH_MAX_FAILED_ATTEMPTS", 5)
    monkeypatch.setattr(m, "REDIS_URL", "redis://broken")

    class BrokenRedisModule:
        class Redis:
            @staticmethod
            def from_url(*_args, **_kwargs):
                raise RuntimeError("bad redis url")

    monkeypatch.setitem(sys.modules, "redis", BrokenRedisModule)

    backend = m._build_backend()

    assert isinstance(backend, m._LocalAuthThrottle)


def test_build_backend_chooses_local_when_no_redis_url(monkeypatch):
    import inbox.auth_throttle as m

    monkeypatch.setattr(m, "INBOX_AUTH_MAX_FAILED_ATTEMPTS", 5)
    monkeypatch.setattr(m, "REDIS_URL", "")

    backend = m._build_backend()

    assert isinstance(backend, m._LocalAuthThrottle)


# ─── Public helpers ────────────────────────────────────────────────────


def test_inbox_auth_keys_are_stable_and_distinct():
    """Same inputs → same hashed keys; ip-only and ip+user keys are distinct."""
    from inbox.auth_throttle import inbox_auth_keys

    keys_1 = inbox_auth_keys("1.2.3.4", "alice")
    keys_2 = inbox_auth_keys("1.2.3.4", "alice")
    keys_3 = inbox_auth_keys("1.2.3.4", "bob")

    assert keys_1 == keys_2
    assert len(keys_1) == 2
    assert keys_1[0] != keys_1[1]  # ip vs ip+user
    # Same IP, different user → ip key shared, ip+user key differs.
    assert keys_1[0] == keys_3[0]
    assert keys_1[1] != keys_3[1]


def test_inbox_auth_keys_normalize_case_and_blanks():
    """Whitespace and case differences must collapse to the same key."""
    from inbox.auth_throttle import inbox_auth_keys

    assert inbox_auth_keys("  1.2.3.4 ", "ALICE") == inbox_auth_keys("1.2.3.4", "alice")
    # Empty values fall back to "unknown".
    assert inbox_auth_keys("", "") == inbox_auth_keys("unknown", "unknown")


def test_public_helpers_drive_the_backend(monkeypatch):
    """is_inbox_auth_limited / record_failure / clear delegate to _backend."""
    import inbox.auth_throttle as m

    class FakeBackend:
        def __init__(self):
            self.is_limited_calls = []
            self.record_calls = []
            self.clear_calls = []
            self.limited_keys = {"k1"}

        def is_limited(self, key):
            self.is_limited_calls.append(key)
            return key in self.limited_keys

        def record_failure(self, key):
            self.record_calls.append(key)
            return key == "trigger"

        def clear(self, key):
            self.clear_calls.append(key)

    fake = FakeBackend()
    monkeypatch.setattr(m, "_backend", fake)

    assert m.is_inbox_auth_limited(["k0", "k1"]) is True
    assert fake.is_limited_calls == ["k0", "k1"]

    assert m.record_inbox_auth_failure(["k0", "trigger"]) is True
    assert fake.record_calls == ["k0", "trigger"]

    m.clear_inbox_auth_failures(["k0", "k1"])
    assert fake.clear_calls == ["k0", "k1"]
