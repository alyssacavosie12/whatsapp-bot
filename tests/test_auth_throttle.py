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
from typing import Any

# ─── _AllowAllAuthThrottle ────────────────────────────────────────────


def test_allow_all_throttle_never_limits_or_records() -> None:
    from inbox.auth_throttle import _AllowAllAuthThrottle

    backend = _AllowAllAuthThrottle()

    assert backend.is_limited("any-key") is False
    assert backend.record_failure("any-key") is False
    backend.clear("any-key")


# ─── _LocalAuthThrottle ───────────────────────────────────────────────


def test_local_throttle_allows_until_threshold_then_limits() -> None:
    from inbox.auth_throttle import _LocalAuthThrottle

    throttle = _LocalAuthThrottle(max_failures=3, window_seconds=60)

    # First two failures: not yet limited.
    assert throttle.record_failure("key") is False
    assert throttle.record_failure("key") is False
    # Third failure crosses the threshold.
    assert throttle.record_failure("key") is True
    assert throttle.is_limited("key") is True


def test_local_throttle_empty_key_is_inert() -> None:
    from inbox.auth_throttle import _LocalAuthThrottle

    throttle = _LocalAuthThrottle(max_failures=3, window_seconds=60)

    assert throttle.is_limited("") is False
    assert throttle.record_failure("") is False
    # Clear on empty key is also a no-op.
    throttle.clear("")


def test_local_throttle_clear_resets_counter() -> None:
    from inbox.auth_throttle import _LocalAuthThrottle

    throttle = _LocalAuthThrottle(max_failures=2, window_seconds=60)

    throttle.record_failure("key")
    throttle.record_failure("key")
    assert throttle.is_limited("key") is True

    throttle.clear("key")
    assert throttle.is_limited("key") is False


def test_local_throttle_resets_counter_when_window_rolls_over(monkeypatch: Any) -> None:
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


def test_local_throttle_evicts_old_bucket_keys(monkeypatch: Any) -> None:
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


def _install_fake_redis(monkeypatch: Any, fake_client: Any) -> Any:
    from core.cache import reset_redis_clients

    class FakeRedisModule:
        class Redis:
            @staticmethod
            def from_url(_url: Any, **_kwargs: Any) -> Any:
                return fake_client

    reset_redis_clients()
    monkeypatch.setitem(sys.modules, "redis", FakeRedisModule)


def test_redis_throttle_records_failure_with_pipeline(monkeypatch: Any) -> None:
    """Redis throttle must batch INCR and EXPIRE in one pipeline round trip."""
    from inbox.auth_throttle import _RedisAuthThrottle

    calls: list[tuple[Any, ...]] = []

    class FakeRedis:
        counter = 0
        last_count = 0

        def pipeline(self) -> Any:
            return self

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *_args: Any) -> Any:
            return False

        def incr(self, key: Any) -> Any:
            calls.append(("incr", key))
            FakeRedis.counter += 1
            FakeRedis.last_count = FakeRedis.counter
            return self

        def expire(self, key: Any, seconds: Any) -> Any:
            calls.append(("expire", key, seconds))
            return self

        def execute(self) -> Any:
            return [FakeRedis.last_count, True]

        def get(self, _key: Any) -> Any:
            return str(FakeRedis.counter)

        def delete(self, _key: Any) -> Any:
            calls.append(("delete",))

    _install_fake_redis(monkeypatch, FakeRedis())
    throttle = _RedisAuthThrottle("redis://example", max_failures=2, window_seconds=42)

    assert throttle.record_failure("key") is False  # count=1, EXPIRE set
    assert throttle.record_failure("key") is True  # count=2 ≥ max
    assert throttle.is_limited("key") is True

    expire_calls = [c for c in calls if c[0] == "expire"]
    assert len(expire_calls) == 2, "EXPIRE must be batched with every INCR"
    assert expire_calls[0][2] == 42


def test_redis_throttle_is_limited_returns_false_when_no_record(monkeypatch: Any) -> None:
    """A key with no recorded failures (`get` returns None) is not limited."""
    from inbox.auth_throttle import _RedisAuthThrottle

    class FakeRedis:
        def get(self, _key: Any) -> Any:
            return None

        def pipeline(self) -> Any:
            return self

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *_args: Any) -> Any:
            return False

        def incr(self, _key: Any) -> Any:
            return self

        def expire(self, *_args: Any) -> Any:
            return self

        def execute(self) -> Any:
            return [1, True]

        def delete(self, *_args: Any) -> Any:
            pass

    _install_fake_redis(monkeypatch, FakeRedis())
    throttle = _RedisAuthThrottle("redis://example", max_failures=3, window_seconds=60)

    assert throttle.is_limited("never-failed") is False


def test_redis_throttle_fails_open_on_redis_error_in_is_limited(monkeypatch: Any) -> None:
    """A Redis outage must allow the auth attempt — log and return not-limited."""
    from inbox.auth_throttle import _RedisAuthThrottle

    class FakeRedis:
        def get(self, _key: Any) -> Any:
            raise OSError("connection refused")

        def pipeline(self) -> Any:
            return self

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *_args: Any) -> Any:
            return False

        def incr(self, _key: Any) -> Any:
            raise OSError("connection refused")

        def expire(self, *_args: Any) -> Any:
            pass

        def delete(self, *_args: Any) -> Any:
            raise OSError("connection refused")

        def execute(self) -> Any:
            return [1, True]

    _install_fake_redis(monkeypatch, FakeRedis())
    throttle = _RedisAuthThrottle("redis://example", max_failures=1, window_seconds=60)

    assert throttle.is_limited("key") is False
    assert throttle.record_failure("key") is False
    # Clear must also not raise even when Redis is down.
    throttle.clear("key")


def test_redis_throttle_clear_calls_delete(monkeypatch: Any) -> None:
    from inbox.auth_throttle import _RedisAuthThrottle

    calls: list[str] = []

    class FakeRedis:
        def get(self, _key: Any) -> Any:
            return None

        def pipeline(self) -> Any:
            return self

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *_args: Any) -> Any:
            return False

        def incr(self, _key: Any) -> Any:
            return self

        def expire(self, *_args: Any) -> Any:
            return self

        def execute(self) -> Any:
            return [1, True]

        def delete(self, key: Any) -> Any:
            calls.append(key)

    _install_fake_redis(monkeypatch, FakeRedis())
    throttle = _RedisAuthThrottle("redis://example", max_failures=3, window_seconds=60)

    throttle.clear("the-key")

    assert calls and calls[0].endswith("the-key")


def test_redis_throttle_empty_key_is_inert(monkeypatch: Any) -> None:
    from inbox.auth_throttle import _RedisAuthThrottle

    class FakeRedis:
        def get(self, _key: Any) -> Any:
            raise AssertionError("get must not be called for empty key")

        def pipeline(self) -> Any:
            raise AssertionError("pipeline must not be called for empty key")

        def incr(self, _key: Any) -> Any:
            raise AssertionError("incr must not be called for empty key")

        def expire(self, *_args: Any) -> Any:
            pass

        def delete(self, *_args: Any) -> Any:
            raise AssertionError("delete must not be called for empty key")

    _install_fake_redis(monkeypatch, FakeRedis())
    throttle = _RedisAuthThrottle("redis://example", max_failures=3, window_seconds=60)

    assert throttle.is_limited("") is False
    assert throttle.record_failure("") is False
    throttle.clear("")


# ─── _build_backend selection logic ───────────────────────────────────


def test_build_backend_returns_allow_all_when_max_failures_zero(monkeypatch: Any) -> None:
    import inbox.auth_throttle as m

    monkeypatch.setattr(m, "INBOX_AUTH_MAX_FAILED_ATTEMPTS", 0)

    backend = m._build_backend()

    assert isinstance(backend, m._AllowAllAuthThrottle)


def test_build_backend_falls_back_to_local_when_redis_init_fails(monkeypatch: Any) -> None:
    import inbox.auth_throttle as m

    monkeypatch.setattr(m, "INBOX_AUTH_MAX_FAILED_ATTEMPTS", 5)
    monkeypatch.setattr(m, "REDIS_URL", "redis://broken")

    class BrokenRedisModule:
        class Redis:
            @staticmethod
            def from_url(*_args: Any, **_kwargs: Any) -> Any:
                raise ValueError("bad redis url")

    monkeypatch.setitem(sys.modules, "redis", BrokenRedisModule)

    backend = m._build_backend()

    assert isinstance(backend, m._LocalAuthThrottle)


def test_build_backend_chooses_local_when_no_redis_url(monkeypatch: Any) -> None:
    import inbox.auth_throttle as m

    monkeypatch.setattr(m, "INBOX_AUTH_MAX_FAILED_ATTEMPTS", 5)
    monkeypatch.setattr(m, "REDIS_URL", "")

    backend = m._build_backend()

    assert isinstance(backend, m._LocalAuthThrottle)


# ─── Public helpers ────────────────────────────────────────────────────


def test_inbox_auth_keys_are_stable_and_distinct() -> None:
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


def test_inbox_auth_keys_normalize_case_and_blanks() -> None:
    """Whitespace and case differences must collapse to the same key."""
    from inbox.auth_throttle import inbox_auth_keys

    assert inbox_auth_keys("  1.2.3.4 ", "ALICE") == inbox_auth_keys("1.2.3.4", "alice")
    # Empty values fall back to "unknown".
    assert inbox_auth_keys("", "") == inbox_auth_keys("unknown", "unknown")


def test_public_helpers_drive_the_backend(monkeypatch: Any) -> None:
    """is_inbox_auth_limited / record_failure / clear delegate to _backend."""
    import inbox.auth_throttle as m

    class FakeBackend:
        def __init__(self) -> None:
            self.is_limited_calls: list[str] = []
            self.record_calls: list[str] = []
            self.clear_calls: list[str] = []
            self.limited_keys = {"k1"}

        def is_limited(self, key: Any) -> Any:
            self.is_limited_calls.append(key)
            return key in self.limited_keys

        def record_failure(self, key: Any) -> Any:
            self.record_calls.append(key)
            return key == "trigger"

        def clear(self, key: Any) -> Any:
            self.clear_calls.append(key)

    fake = FakeBackend()
    monkeypatch.setattr(m, "_backend", fake)

    assert m.is_inbox_auth_limited(["k0", "k1"]) is True
    assert fake.is_limited_calls == ["k0", "k1"]

    assert m.record_inbox_auth_failure(["k0", "trigger"]) is True
    assert fake.record_calls == ["k0", "trigger"]

    m.clear_inbox_auth_failures(["k0", "k1"])
    assert fake.clear_calls == ["k0", "k1"]
