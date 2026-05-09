"""Webhook message dedup.

Backed by Redis when REDIS_URL is set so dedup is shared across gunicorn
workers and pods. Otherwise falls back to a thread-safe, bounded in-memory
LRU cache that survives within a single process only.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from typing import Final, Protocol

from core.cache import REDIS_OPERATION_ERRORS, get_redis
from settings import MAX_LOCAL_DEDUP_SIZE, MESSAGE_TTL_SECONDS, REDIS_URL

logger = logging.getLogger(__name__)

REDIS_KEY_PREFIX: Final = "wa:msg:"


class _DedupBackend(Protocol):
    def seen(self, key: str) -> bool: ...


class _LocalDedup:
    """Thread-safe in-memory dedup with TTL and a hard size cap (LRU eviction)."""

    def __init__(self, max_size: int, ttl_seconds: int) -> None:
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._items: OrderedDict[str, float] = OrderedDict()

    def seen(self, key: str) -> bool:
        if not key:
            return False

        now = time.time()

        with self._lock:
            existing = self._items.get(key)
            if existing is not None and now - existing <= self._ttl:
                self._items.move_to_end(key)
                return True

            self._items[key] = now
            self._items.move_to_end(key)
            self._evict(now)
            return False

    def _evict(self, now: float) -> None:
        while self._items:
            oldest_key = next(iter(self._items))
            oldest_ts = self._items[oldest_key]
            over_cap = len(self._items) > self._max_size
            expired = now - oldest_ts > self._ttl

            if not over_cap and not expired:
                return

            self._items.popitem(last=False)


class _RedisDedup:
    """Atomic Redis-backed dedup using SET NX EX. Fails open on Redis errors."""

    def __init__(self, url: str, ttl_seconds: int) -> None:
        get_redis(url)
        self._url = url
        self._ttl = ttl_seconds

    def seen(self, key: str) -> bool:
        if not key:
            return False

        try:
            stored = get_redis(self._url).set(
                REDIS_KEY_PREFIX + key,
                "1",
                nx=True,
                ex=self._ttl,
            )
        except REDIS_OPERATION_ERRORS as exc:
            logger.error(
                "Redis dedup unavailable, allowing message: %s",
                exc.__class__.__name__,
            )
            return False

        return not stored


def _build_backend() -> _DedupBackend:
    if REDIS_URL:
        try:
            return _RedisDedup(REDIS_URL, MESSAGE_TTL_SECONDS)
        except REDIS_OPERATION_ERRORS as exc:
            logger.error(
                "Failed to initialize Redis dedup, using local fallback: %s",
                exc.__class__.__name__,
            )

    return _LocalDedup(MAX_LOCAL_DEDUP_SIZE, MESSAGE_TTL_SECONDS)


_backend: _DedupBackend = _build_backend()


def seen_message(message_id: str) -> bool:
    """Return True if this message_id was already processed within TTL."""
    return _backend.seen(message_id)
