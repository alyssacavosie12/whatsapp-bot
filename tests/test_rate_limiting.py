"""Rate-limiting tests: per-phone fixed-window limiter and per-IP webhook limit.

The per-phone limiter has three backends in webhook/rate_limit.py:
- `_AllowAllRateLimiter` (when max_events == 0)
- `_LocalFixedWindowRateLimiter` (in-memory, dev/single-worker)
- `_RedisFixedWindowRateLimiter` (Redis INCR+EXPIRE, multi-worker)

The per-IP limit is built by `webhook.http_hardening.build_webhook_rate_limit`
and applied as a decorator on the /webhook route. This file covers both:
the limiter classes get unit tests, and a single integration test confirms
that exhausting the IP limit returns 429 from /webhook.
"""

from __future__ import annotations

import time
from typing import Any

# ─── Per-phone: _LocalFixedWindowRateLimiter ─────────────────────────


def test_local_limiter_allows_up_to_max_events() -> None:
    from webhook.rate_limit import _LocalFixedWindowRateLimiter

    limiter = _LocalFixedWindowRateLimiter(max_events=3, window_seconds=60)

    assert [limiter.allow("phone-1") for _ in range(3)] == [True, True, True]


def test_local_limiter_blocks_after_max_events() -> None:
    from webhook.rate_limit import _LocalFixedWindowRateLimiter

    limiter = _LocalFixedWindowRateLimiter(max_events=3, window_seconds=60)

    for _ in range(3):
        limiter.allow("phone-1")

    assert limiter.allow("phone-1") is False
    assert limiter.allow("phone-1") is False


def test_local_limiter_separates_keys() -> None:
    """Per-phone limit must be per-key — one chatty number doesn't block others."""
    from webhook.rate_limit import _LocalFixedWindowRateLimiter

    limiter = _LocalFixedWindowRateLimiter(max_events=2, window_seconds=60)

    limiter.allow("phone-1")
    limiter.allow("phone-1")
    assert limiter.allow("phone-1") is False
    assert limiter.allow("phone-2") is True


def test_local_limiter_resets_after_window_passes(monkeypatch: Any) -> None:
    from webhook.rate_limit import _LocalFixedWindowRateLimiter

    limiter = _LocalFixedWindowRateLimiter(max_events=2, window_seconds=60)
    base = 1_000_000.0
    monkeypatch.setattr(time, "time", lambda: base)

    limiter.allow("phone-1")
    limiter.allow("phone-1")
    assert limiter.allow("phone-1") is False

    monkeypatch.setattr(time, "time", lambda: base + 60)
    assert limiter.allow("phone-1") is True


def test_local_limiter_evicts_old_buckets_to_avoid_unbounded_memory(monkeypatch: Any) -> None:
    """Old keys from previous windows must not stay in the dict forever."""
    from webhook.rate_limit import _LocalFixedWindowRateLimiter

    limiter = _LocalFixedWindowRateLimiter(max_events=5, window_seconds=10)

    monkeypatch.setattr(time, "time", lambda: 1_000_000.0)
    limiter.allow("phone-old")

    monkeypatch.setattr(time, "time", lambda: 1_000_020.0)  # two windows later
    limiter.allow("phone-new")

    assert "phone-old" not in limiter._counters
    assert "phone-new" in limiter._counters


def test_local_limiter_rejects_empty_key() -> None:
    """Empty key (e.g. a dropped sender id) must not bypass the limiter."""
    from webhook.rate_limit import _LocalFixedWindowRateLimiter

    limiter = _LocalFixedWindowRateLimiter(max_events=10, window_seconds=60)

    assert limiter.allow("") is False


# ─── Per-phone: _RedisFixedWindowRateLimiter ─────────────────────────


def _install_fake_redis(monkeypatch: Any, fake_client: Any) -> Any:
    from core.cache import reset_redis_clients

    class FakeRedisModule:
        class Redis:
            @staticmethod
            def from_url(_url: Any, **_kwargs: Any) -> Any:
                return fake_client

    import sys

    reset_redis_clients()
    monkeypatch.setitem(sys.modules, "redis", FakeRedisModule)


def test_redis_limiter_uses_pipeline_for_incr_and_expire(monkeypatch: Any) -> None:
    """Redis limiter must batch INCR and EXPIRE in one pipeline round trip."""
    from webhook.rate_limit import _RedisFixedWindowRateLimiter

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

    _install_fake_redis(monkeypatch, FakeRedis())
    limiter = _RedisFixedWindowRateLimiter("redis://example", max_events=2, window_seconds=42)

    assert limiter.allow("phone-1") is True
    assert limiter.allow("phone-1") is True
    assert limiter.allow("phone-1") is False

    incr_calls = [c for c in calls if c[0] == "incr"]
    expire_calls = [c for c in calls if c[0] == "expire"]
    assert len(incr_calls) == 3
    assert len(expire_calls) == 3, "EXPIRE must be batched with every INCR"
    assert expire_calls[0][2] == 42


def test_redis_limiter_fails_open_when_redis_is_down(monkeypatch: Any) -> None:
    """A Redis outage must not drop legit messages — log and allow."""
    from webhook.rate_limit import _RedisFixedWindowRateLimiter

    class FakeRedis:
        def pipeline(self) -> Any:
            return self

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *_args: Any) -> Any:
            return False

        def incr(self, _key: Any) -> Any:
            raise OSError("connection refused")

        def expire(self, *_args: Any, **_kwargs: Any) -> Any:
            pass

        def execute(self) -> Any:
            return [1, True]

    _install_fake_redis(monkeypatch, FakeRedis())
    limiter = _RedisFixedWindowRateLimiter("redis://example", max_events=1, window_seconds=60)

    assert limiter.allow("phone-1") is True


# ─── Per-phone: _AllowAllRateLimiter (max_events=0) ──────────────────


def test_disabled_phone_limiter_always_allows(monkeypatch: Any) -> None:
    """Setting PHONE_RATE_LIMIT_MAX_MESSAGES=0 selects the allow-all backend."""
    import webhook.rate_limit as rl
    from webhook.rate_limit import _AllowAllRateLimiter

    monkeypatch.setattr(rl, "PHONE_RATE_LIMIT_MAX_MESSAGES", 0)
    backend = rl._build_backend()

    assert isinstance(backend, _AllowAllRateLimiter)
    for _ in range(1000):
        assert backend.allow("phone-1") is True


# ─── Per-IP webhook limit: integration test ─────────────────────────


def test_webhook_returns_429_when_ip_rate_limit_exceeded(
    content_file: Any, monkeypatch: Any
) -> None:
    """Exhausting the per-IP webhook rate limit returns 429.

    The /webhook route is wrapped with the rate-limiter decorator that
    `create_app()` builds from `app.WEBHOOK_RATE_LIMIT`. We monkeypatch
    that value to a tiny limit and call `create_app()` so the decorator
    picks it up.
    """
    import app as app_module
    from webhook import signature as webhook_signature

    monkeypatch.setattr(app_module, "WEBHOOK_RATE_LIMIT", "2 per minute")
    monkeypatch.setattr(app_module, "RATE_LIMIT_STORAGE_URL", "")

    flask_app = app_module.create_app()
    monkeypatch.setattr(webhook_signature, "verify_meta_signature", lambda: True)

    client = flask_app.test_client()
    payload = {"entry": [{"changes": [{"value": {"statuses": [{"id": "1"}]}}]}]}

    first = client.post("/webhook", json=payload)
    second = client.post("/webhook", json=payload)
    third = client.post("/webhook", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429, (
        f"Third request must be rate-limited; got {third.status_code} with body {third.data!r}"
    )
