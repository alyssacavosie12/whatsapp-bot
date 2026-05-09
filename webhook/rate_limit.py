"""Per-phone webhook rate limiting.

Uses Redis when REDIS_URL is configured so limits are shared across workers.
Falls back to an in-memory fixed-window limiter for local/single-worker runs.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Final, Protocol, cast

from core.cache import REDIS_OPERATION_ERRORS, get_redis
from settings import (
    PHONE_RATE_LIMIT_MAX_MESSAGES,
    PHONE_RATE_LIMIT_WINDOW_SECONDS,
    REDIS_URL,
)

logger = logging.getLogger(__name__)

REDIS_KEY_PREFIX: Final = "wa:rate:"


class _RateLimitBackend(Protocol):
    def allow(self, key: str) -> bool: ...


class _AllowAllRateLimiter:
    def allow(self, key: str) -> bool:
        return True


class _LocalFixedWindowRateLimiter:
    """Thread-safe fixed-window limiter for dev and single-process deploys."""

    def __init__(self, max_events: int, window_seconds: int) -> None:
        self._max_events = max_events
        self._window_seconds = window_seconds
        self._lock = threading.Lock()
        self._counters: dict[str, tuple[int, int]] = {}

    def allow(self, key: str) -> bool:
        if not key:
            return False

        bucket = self._current_bucket()

        with self._lock:
            count, stored_bucket = self._counters.get(key, (0, bucket))

            if stored_bucket != bucket:
                count = 0
                stored_bucket = bucket

            count += 1
            self._counters[key] = (count, stored_bucket)
            self._evict_old_buckets(bucket)

            return count <= self._max_events

    def _current_bucket(self) -> int:
        return int(time.time() // self._window_seconds)

    def _evict_old_buckets(self, current_bucket: int) -> None:
        for key, (_, bucket) in list(self._counters.items()):
            if bucket < current_bucket:
                self._counters.pop(key, None)


class _RedisFixedWindowRateLimiter:
    """Fixed-window limiter backed by Redis INCR + EXPIRE."""

    def __init__(self, url: str, max_events: int, window_seconds: int) -> None:
        get_redis(url)
        self._url = url
        self._max_events = max_events
        self._window_seconds = window_seconds

    def allow(self, key: str) -> bool:
        if not key:
            return False

        bucket = int(time.time() // self._window_seconds)
        redis_key = f"{REDIS_KEY_PREFIX}{key}:{bucket}"

        try:
            with get_redis(self._url).pipeline() as pipe:
                pipe.incr(redis_key)
                pipe.expire(redis_key, self._window_seconds)
                count = cast(list[int], pipe.execute())[0]
        except REDIS_OPERATION_ERRORS as exc:
            logger.error(
                "Redis rate limit unavailable, allowing message: %s",
                exc.__class__.__name__,
            )
            return True

        return int(count) <= self._max_events


def _build_backend() -> _RateLimitBackend:
    max_events = max(0, PHONE_RATE_LIMIT_MAX_MESSAGES)
    window_seconds = max(1, PHONE_RATE_LIMIT_WINDOW_SECONDS)

    if max_events == 0:
        return _AllowAllRateLimiter()

    if REDIS_URL:
        try:
            return _RedisFixedWindowRateLimiter(
                REDIS_URL,
                max_events,
                window_seconds,
            )
        except REDIS_OPERATION_ERRORS as exc:
            logger.error(
                "Failed to initialize Redis rate limit, using local fallback: %s",
                exc.__class__.__name__,
            )

    return _LocalFixedWindowRateLimiter(max_events, window_seconds)


_backend: _RateLimitBackend = _build_backend()


def allow_phone_message(phone: str) -> bool:
    """Return True when a sender is still within the configured message limit."""
    return _backend.allow(phone)
