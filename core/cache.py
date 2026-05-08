"""Shared Redis clients backed by connection pools."""

from __future__ import annotations

import logging
from typing import Any

from settings import (
    REDIS_HEALTH_CHECK_INTERVAL_SECONDS,
    REDIS_MAX_CONNECTIONS,
    REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS,
    REDIS_SOCKET_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

_REDIS_CLIENTS: dict[str, Any] = {}
_REDIS_POOLS: dict[str, Any] = {}


def get_redis(url: str) -> Any:
    """Return a Redis client backed by a shared connection pool.

    Args:
        url: Redis connection URL, including credentials when required.
    """
    if not url:
        raise ValueError("Redis URL is required")

    client = _REDIS_CLIENTS.get(url)
    if client is not None:
        return client

    import redis

    connection_pool = getattr(redis, "ConnectionPool", None)
    pool_from_url = getattr(connection_pool, "from_url", None)

    if callable(pool_from_url):
        pool = pool_from_url(
            url,
            max_connections=REDIS_MAX_CONNECTIONS,
            socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
            socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS,
            retry_on_timeout=True,
            health_check_interval=REDIS_HEALTH_CHECK_INTERVAL_SECONDS,
            decode_responses=True,
        )
        client = redis.Redis(connection_pool=pool)
        _REDIS_POOLS[url] = pool
    else:
        logger.warning("Redis ConnectionPool unavailable; using direct client fallback")
        client = redis.Redis.from_url(
            url,
            socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
            socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS,
            decode_responses=True,
        )

    _REDIS_CLIENTS[url] = client
    return client


def safe_redis_get(url: str, key: str) -> str | None:
    """Return a Redis value, or None when Redis is unavailable."""
    try:
        value = get_redis(url).get(key)
    except Exception as exc:
        logger.error("redis_get_failed key=%s error=%s", key, exc.__class__.__name__)
        return None

    if isinstance(value, bytes):
        return value.decode("utf-8")

    if value is None:
        return None

    return str(value)


def safe_redis_setex(url: str, key: str, ttl_seconds: int, value: Any) -> bool:
    """Set a Redis key with TTL, returning False when Redis is unavailable."""
    try:
        get_redis(url).setex(key, ttl_seconds, value)
    except Exception as exc:
        logger.error("redis_set_failed key=%s error=%s", key, exc.__class__.__name__)
        return False

    return True


def reset_redis_clients() -> None:
    """Clear cached Redis clients and disconnect any open pools."""
    for pool in _REDIS_POOLS.values():
        disconnect = getattr(pool, "disconnect", None)
        if callable(disconnect):
            disconnect()

    _REDIS_CLIENTS.clear()
    _REDIS_POOLS.clear()
