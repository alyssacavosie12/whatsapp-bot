"""Rate limiting for admin inbox authentication attempts."""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Final, Protocol, cast

from core.cache import REDIS_OPERATION_ERRORS, get_redis
from settings import (
    INBOX_AUTH_MAX_FAILED_ATTEMPTS,
    INBOX_AUTH_WINDOW_SECONDS,
    REDIS_URL,
)

logger = logging.getLogger(__name__)

REDIS_KEY_PREFIX: Final = "inbox:auth:"


class _AuthThrottleBackend(Protocol):
    def is_limited(self, key: str) -> bool: ...
    def record_failure(self, key: str) -> bool: ...
    def clear(self, key: str) -> None: ...


class _AllowAllAuthThrottle:
    def is_limited(self, key: str) -> bool:
        return False

    def record_failure(self, key: str) -> bool:
        return False

    def clear(self, key: str) -> None:
        return None


class _LocalAuthThrottle:
    """Thread-safe fixed-window failed-login limiter."""

    def __init__(self, max_failures: int, window_seconds: int) -> None:
        self._max_failures = max_failures
        self._window_seconds = window_seconds
        self._lock = threading.Lock()
        self._failures: dict[str, tuple[int, int]] = {}

    def is_limited(self, key: str) -> bool:
        if not key:
            return False

        bucket = self._current_bucket()
        with self._lock:
            count, stored_bucket = self._failures.get(key, (0, bucket))
            if stored_bucket != bucket:
                self._failures.pop(key, None)
                return False

            return count >= self._max_failures

    def record_failure(self, key: str) -> bool:
        if not key:
            return False

        bucket = self._current_bucket()
        with self._lock:
            count, stored_bucket = self._failures.get(key, (0, bucket))
            if stored_bucket != bucket:
                count = 0
                stored_bucket = bucket

            count += 1
            self._failures[key] = (count, stored_bucket)
            self._evict_old_buckets(bucket)

            return count >= self._max_failures

    def clear(self, key: str) -> None:
        if not key:
            return

        with self._lock:
            self._failures.pop(key, None)

    def _current_bucket(self) -> int:
        return int(time.time() // self._window_seconds)

    def _evict_old_buckets(self, current_bucket: int) -> None:
        for key, (_, bucket) in list(self._failures.items()):
            if bucket < current_bucket:
                self._failures.pop(key, None)


class _RedisAuthThrottle:
    """Redis-backed fixed-window failed-login limiter."""

    def __init__(self, url: str, max_failures: int, window_seconds: int) -> None:
        get_redis(url)
        self._url = url
        self._max_failures = max_failures
        self._window_seconds = window_seconds

    def is_limited(self, key: str) -> bool:
        if not key:
            return False

        try:
            value = cast(
                bytes | str | int | None,
                get_redis(self._url).get(self._redis_key(key)),
            )
        except REDIS_OPERATION_ERRORS as exc:
            logger.error(
                "Redis auth throttle unavailable, allowing auth attempt: %s",
                exc.__class__.__name__,
            )
            return False

        if not value:
            return False

        return int(value) >= self._max_failures

    def record_failure(self, key: str) -> bool:
        if not key:
            return False

        redis_key = self._redis_key(key)
        try:
            with get_redis(self._url).pipeline() as pipe:
                pipe.incr(redis_key)
                pipe.expire(redis_key, self._window_seconds)
                count = cast(list[int], pipe.execute())[0]
        except REDIS_OPERATION_ERRORS as exc:
            logger.error(
                "Redis auth throttle unavailable, allowing auth attempt: %s",
                exc.__class__.__name__,
            )
            return False

        return int(count) >= self._max_failures

    def clear(self, key: str) -> None:
        if not key:
            return

        try:
            get_redis(self._url).delete(self._redis_key(key))
        except REDIS_OPERATION_ERRORS as exc:
            logger.error(
                "Redis auth throttle clear failed: %s",
                exc.__class__.__name__,
            )

    def _redis_key(self, key: str) -> str:
        return REDIS_KEY_PREFIX + key


def _build_backend() -> _AuthThrottleBackend:
    max_failures = max(0, INBOX_AUTH_MAX_FAILED_ATTEMPTS)
    window_seconds = max(1, INBOX_AUTH_WINDOW_SECONDS)

    if max_failures == 0:
        return _AllowAllAuthThrottle()

    if REDIS_URL:
        try:
            return _RedisAuthThrottle(REDIS_URL, max_failures, window_seconds)
        except REDIS_OPERATION_ERRORS as exc:
            logger.error(
                "Failed to initialize Redis auth throttle, using local fallback: %s",
                exc.__class__.__name__,
            )

    return _LocalAuthThrottle(max_failures, window_seconds)


_backend: _AuthThrottleBackend = _build_backend()


def inbox_auth_keys(ip_address: str, username: str) -> list[str]:
    """Return hashed throttle keys for an IP and IP+username pair."""
    safe_ip = str(ip_address or "unknown").strip().lower()
    safe_username = str(username or "unknown").strip().lower()

    return [
        hashlib.sha256(f"ip:{safe_ip}".encode()).hexdigest(),
        hashlib.sha256(f"ip-user:{safe_ip}:{safe_username}".encode()).hexdigest(),
    ]


def is_inbox_auth_limited(keys: list[str]) -> bool:
    """Return True when any throttle key is over the failed-login limit."""
    return any(_backend.is_limited(key) for key in keys)


def record_inbox_auth_failure(keys: list[str]) -> bool:
    """Record a failed inbox login attempt and return True if now limited."""
    limited = False
    for key in keys:
        limited = _backend.record_failure(key) or limited

    return limited


def clear_inbox_auth_failures(keys: list[str]) -> None:
    """Clear failed-login counters after a successful inbox login."""
    for key in keys:
        _backend.clear(key)
