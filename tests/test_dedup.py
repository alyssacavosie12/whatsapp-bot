from __future__ import annotations

import time

import pytest

from dedup import _LocalDedup


def test_local_dedup_first_seen_is_false():
    cache = _LocalDedup(max_size=10, ttl_seconds=60)
    assert cache.seen("abc") is False


def test_local_dedup_repeated_message_is_true():
    cache = _LocalDedup(max_size=10, ttl_seconds=60)
    cache.seen("abc")
    assert cache.seen("abc") is True


def test_local_dedup_empty_key_never_seen():
    cache = _LocalDedup(max_size=10, ttl_seconds=60)
    assert cache.seen("") is False
    assert cache.seen("") is False


def test_local_dedup_evicts_when_over_capacity():
    cache = _LocalDedup(max_size=3, ttl_seconds=60)

    for key in ("a", "b", "c", "d"):
        cache.seen(key)

    # "a" should have been evicted (oldest, over cap)
    assert cache.seen("a") is False
    assert cache.seen("d") is True


def test_local_dedup_capacity_strictly_bounded():
    cache = _LocalDedup(max_size=5, ttl_seconds=60)

    for i in range(1000):
        cache.seen(f"id-{i}")

    assert len(cache._items) <= 5


def test_local_dedup_evicts_expired_entries(monkeypatch):
    cache = _LocalDedup(max_size=10, ttl_seconds=1)

    base = 1_000_000.0
    monkeypatch.setattr(time, "time", lambda: base)
    cache.seen("old")

    monkeypatch.setattr(time, "time", lambda: base + 5)
    assert cache.seen("old") is False
    assert "old" in cache._items


def test_redis_backend_uses_set_nx_ex(monkeypatch):
    """RedisDedup must call SET with NX and EX so dedup is atomic and TTL'd."""
    from dedup import _RedisDedup

    calls = []

    class FakeRedis:
        def set(self, key, value, nx=False, ex=None):
            calls.append({"key": key, "value": value, "nx": nx, "ex": ex})
            return True if len(calls) == 1 else None  # first stores, second collides

    class FakeRedisModule:
        class Redis:
            @staticmethod
            def from_url(url, **_kwargs):
                return FakeRedis()

    monkeypatch.setitem(__import__("sys").modules, "redis", FakeRedisModule)

    dedup = _RedisDedup("redis://example", ttl_seconds=42)

    assert dedup.seen("msg-1") is False
    assert dedup.seen("msg-1") is True
    assert calls[0]["nx"] is True
    assert calls[0]["ex"] == 42
    assert calls[0]["key"].endswith("msg-1")


def test_redis_backend_fails_open_on_error(monkeypatch):
    from dedup import _RedisDedup

    class FakeRedis:
        def set(self, *_args, **_kwargs):
            raise RuntimeError("connection refused")

    class FakeRedisModule:
        class Redis:
            @staticmethod
            def from_url(url, **_kwargs):
                return FakeRedis()

    monkeypatch.setitem(__import__("sys").modules, "redis", FakeRedisModule)

    dedup = _RedisDedup("redis://example", ttl_seconds=10)
    assert dedup.seen("msg-1") is False  # fail-open, don't drop legit messages
