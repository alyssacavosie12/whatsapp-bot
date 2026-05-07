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

import importlib
import time

import pytest


# ─── Per-phone: _LocalFixedWindowRateLimiter ─────────────────────────


def test_local_limiter_allows_up_to_max_events():
    from webhook.rate_limit import _LocalFixedWindowRateLimiter

    limiter = _LocalFixedWindowRateLimiter(max_events=3, window_seconds=60)

    assert [limiter.allow("phone-1") for _ in range(3)] == [True, True, True]


def test_local_limiter_blocks_after_max_events():
    from webhook.rate_limit import _LocalFixedWindowRateLimiter

    limiter = _LocalFixedWindowRateLimiter(max_events=3, window_seconds=60)

    for _ in range(3):
        limiter.allow("phone-1")

    assert limiter.allow("phone-1") is False
    assert limiter.allow("phone-1") is False


def test_local_limiter_separates_keys():
    """Per-phone limit must be per-key — one chatty number doesn't block others."""
    from webhook.rate_limit import _LocalFixedWindowRateLimiter

    limiter = _LocalFixedWindowRateLimiter(max_events=2, window_seconds=60)

    limiter.allow("phone-1")
    limiter.allow("phone-1")
    assert limiter.allow("phone-1") is False
    assert limiter.allow("phone-2") is True


def test_local_limiter_resets_after_window_passes(monkeypatch):
    from webhook.rate_limit import _LocalFixedWindowRateLimiter

    limiter = _LocalFixedWindowRateLimiter(max_events=2, window_seconds=60)
    base = 1_000_000.0
    monkeypatch.setattr(time, "time", lambda: base)

    limiter.allow("phone-1")
    limiter.allow("phone-1")
    assert limiter.allow("phone-1") is False

    monkeypatch.setattr(time, "time", lambda: base + 60)
    assert limiter.allow("phone-1") is True


def test_local_limiter_evicts_old_buckets_to_avoid_unbounded_memory(monkeypatch):
    """Old keys from previous windows must not stay in the dict forever."""
    from webhook.rate_limit import _LocalFixedWindowRateLimiter

    limiter = _LocalFixedWindowRateLimiter(max_events=5, window_seconds=10)

    monkeypatch.setattr(time, "time", lambda: 1_000_000.0)
    limiter.allow("phone-old")

    monkeypatch.setattr(time, "time", lambda: 1_000_020.0)  # two windows later
    limiter.allow("phone-new")

    assert "phone-old" not in limiter._counters
    assert "phone-new" in limiter._counters


def test_local_limiter_rejects_empty_key():
    """Empty key (e.g. a dropped sender id) must not bypass the limiter."""
    from webhook.rate_limit import _LocalFixedWindowRateLimiter

    limiter = _LocalFixedWindowRateLimiter(max_events=10, window_seconds=60)

    assert limiter.allow("") is False


# ─── Per-phone: _RedisFixedWindowRateLimiter ─────────────────────────


def _install_fake_redis(monkeypatch, fake_client):
    class FakeRedisModule:
        class Redis:
            @staticmethod
            def from_url(_url, **_kwargs):
                return fake_client

    import sys
    monkeypatch.setitem(sys.modules, "redis", FakeRedisModule)


def test_redis_limiter_uses_incr_and_sets_expire_on_first_event(monkeypatch):
    """First event in a bucket must INCR and EXPIRE so the key actually times out."""
    from webhook.rate_limit import _RedisFixedWindowRateLimiter

    calls = []

    class FakeRedis:
        counter = 0

        def incr(self, key):
            calls.append(("incr", key))
            FakeRedis.counter += 1
            return FakeRedis.counter

        def expire(self, key, seconds):
            calls.append(("expire", key, seconds))

    _install_fake_redis(monkeypatch, FakeRedis())
    limiter = _RedisFixedWindowRateLimiter(
        "redis://example", max_events=2, window_seconds=42
    )

    assert limiter.allow("phone-1") is True
    assert limiter.allow("phone-1") is True
    assert limiter.allow("phone-1") is False

    incr_calls = [c for c in calls if c[0] == "incr"]
    expire_calls = [c for c in calls if c[0] == "expire"]
    assert len(incr_calls) == 3
    assert len(expire_calls) == 1, "EXPIRE must be set exactly once per bucket"
    assert expire_calls[0][2] == 42


def test_redis_limiter_fails_open_when_redis_is_down(monkeypatch):
    """A Redis outage must not drop legit messages — log and allow."""
    from webhook.rate_limit import _RedisFixedWindowRateLimiter

    class FakeRedis:
        def incr(self, _key):
            raise RuntimeError("connection refused")

        def expire(self, *_args, **_kwargs):
            pass

    _install_fake_redis(monkeypatch, FakeRedis())
    limiter = _RedisFixedWindowRateLimiter(
        "redis://example", max_events=1, window_seconds=60
    )

    assert limiter.allow("phone-1") is True


# ─── Per-phone: _AllowAllRateLimiter (max_events=0) ──────────────────


def test_disabled_phone_limiter_always_allows(monkeypatch):
    """Setting PHONE_RATE_LIMIT_MAX_MESSAGES=0 selects the allow-all backend."""
    import webhook.rate_limit as rl
    from webhook.rate_limit import _AllowAllRateLimiter

    monkeypatch.setattr(rl, "PHONE_RATE_LIMIT_MAX_MESSAGES", 0)
    backend = rl._build_backend()

    assert isinstance(backend, _AllowAllRateLimiter)
    for _ in range(1000):
        assert backend.allow("phone-1") is True


# ─── Per-IP webhook limit: integration test ─────────────────────────


def test_webhook_returns_429_when_ip_rate_limit_exceeded(content_file, monkeypatch):
    """Exhausting the per-IP webhook rate limit returns 429.

    The /webhook route is decorated with `@webhook_rate_limit`, which is
    built from `settings.WEBHOOK_RATE_LIMIT` at import time. We monkeypatch
    settings to a tiny limit and reload `app` so the decorator picks it up.
    """
    import settings

    monkeypatch.setattr(settings, "WEBHOOK_RATE_LIMIT", "2 per minute")
    monkeypatch.setattr(settings, "RATE_LIMIT_STORAGE_URL", "")

    import app
    app_module = importlib.reload(app)
    monkeypatch.setattr(app_module, "verify_meta_signature", lambda: True)

    client = app_module.app.test_client()
    payload = {"entry": [{"changes": [{"value": {"statuses": [{"id": "1"}]}}]}]}

    first = client.post("/webhook", json=payload)
    second = client.post("/webhook", json=payload)
    third = client.post("/webhook", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429, (
        f"Third request must be rate-limited; got {third.status_code} "
        f"with body {third.data!r}"
    )
