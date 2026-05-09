"""Shared Redis clients backed by connection pools."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final, cast

from flask import current_app, has_app_context

from core.dependency_keys import REDIS_MANAGER_EXTENSION_KEY
from settings import (
    REDIS_HEALTH_CHECK_INTERVAL_SECONDS,
    REDIS_MAX_CONNECTIONS,
    REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS,
    REDIS_SOCKET_TIMEOUT_SECONDS,
)

if TYPE_CHECKING:
    from redis import Redis as RedisClient
    from redis.connection import ConnectionPool

type RedisClientT = RedisClient
type ConnectionPoolT = ConnectionPool

logger = logging.getLogger(__name__)

_REDIS_ERROR_TYPE: type[BaseException]
try:
    from redis.exceptions import RedisError as _ImportedRedisError
except ImportError:
    _REDIS_ERROR_TYPE = RuntimeError
else:
    _REDIS_ERROR_TYPE = _ImportedRedisError

REDIS_OPERATION_ERRORS: Final[tuple[type[BaseException], ...]] = (
    _REDIS_ERROR_TYPE,
    ImportError,
    ConnectionError,
    OSError,
    TimeoutError,
    TypeError,
    ValueError,
)


@dataclass(frozen=True)
class RedisClientSettings:
    """Configuration for shared Redis clients."""

    max_connections: int = REDIS_MAX_CONNECTIONS
    socket_timeout_seconds: float = REDIS_SOCKET_TIMEOUT_SECONDS
    socket_connect_timeout_seconds: float = REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS
    health_check_interval_seconds: int = REDIS_HEALTH_CHECK_INTERVAL_SECONDS

    # When True, prefer BlockingConnectionPool so requests wait for an
    # available Redis connection instead of immediately failing when the pool is
    # exhausted. Keep False by default to preserve existing behavior.
    use_blocking_pool: bool = False


@dataclass
class RedisClientManager:
    """Own Redis clients and connection pools for one application runtime."""

    settings: RedisClientSettings = field(default_factory=RedisClientSettings)
    _clients: dict[str, RedisClientT] = field(default_factory=dict)
    _pools: dict[str, ConnectionPoolT] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def get_client(self, url: str) -> RedisClientT:
        """Return a Redis client backed by a shared connection pool."""
        if not url:
            raise ValueError("Redis URL is required")

        client = self._clients.get(url)
        if client is not None:
            return client

        with self._lock:
            # Another thread may have created the client while this thread was
            # waiting for the lock.
            client = self._clients.get(url)
            if client is not None:
                return client

            client = self._create_client(url)
            self._clients[url] = client
            return client

    def _create_client(self, url: str) -> RedisClientT:
        """Create one Redis client for a URL."""
        import redis

        pool_class = self._connection_pool_class(redis)
        pool_from_url = getattr(pool_class, "from_url", None)

        if callable(pool_from_url):
            pool = pool_from_url(
                url,
                max_connections=self.settings.max_connections,
                socket_timeout=self.settings.socket_timeout_seconds,
                socket_connect_timeout=self.settings.socket_connect_timeout_seconds,
                retry_on_timeout=True,
                health_check_interval=self.settings.health_check_interval_seconds,
                decode_responses=True,
            )
            client = redis.Redis(connection_pool=pool)
            self._pools[url] = pool
            return client

        logger.warning("Redis ConnectionPool unavailable; using direct client fallback")
        client = redis.Redis.from_url(
            url,
            socket_timeout=self.settings.socket_timeout_seconds,
            socket_connect_timeout=self.settings.socket_connect_timeout_seconds,
            decode_responses=True,
        )
        return client

    def _connection_pool_class(self, redis_module: Any) -> Any:
        """Return the preferred Redis connection pool class."""
        if self.settings.use_blocking_pool:
            blocking_pool = getattr(redis_module, "BlockingConnectionPool", None)
            if blocking_pool is not None:
                return blocking_pool

            logger.warning("Redis BlockingConnectionPool unavailable; using ConnectionPool")

        return getattr(redis_module, "ConnectionPool", None)

    def reset(self) -> None:
        """Clear cached Redis clients and disconnect any open pools."""
        with self._lock:
            for pool in self._pools.values():
                disconnect = getattr(pool, "disconnect", None)
                if callable(disconnect):
                    disconnect()

            self._clients.clear()
            self._pools.clear()


_DEFAULT_REDIS_MANAGER = RedisClientManager()


def _current_redis_manager() -> RedisClientManager:
    """Return the app-injected Redis manager or the CLI fallback."""
    if has_app_context():
        app = cast(Any, current_app)._get_current_object()
        manager = app.extensions.get(REDIS_MANAGER_EXTENSION_KEY)
        if manager is not None:
            return cast(RedisClientManager, manager)

    return _DEFAULT_REDIS_MANAGER


def get_redis(url: str) -> RedisClientT:
    """Return a Redis client backed by a shared connection pool.

    Args:
        url: Redis connection URL, including credentials when required.
    """
    return _current_redis_manager().get_client(url)


def safe_redis_get(url: str, key: str) -> str | None:
    """Return a Redis value, or None when Redis is unavailable."""
    try:
        value = get_redis(url).get(key)
    except REDIS_OPERATION_ERRORS as exc:
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
    except REDIS_OPERATION_ERRORS as exc:
        logger.error("redis_set_failed key=%s error=%s", key, exc.__class__.__name__)
        return False

    return True


def reset_redis_clients() -> None:
    """Clear cached Redis clients and disconnect any open pools."""
    _current_redis_manager().reset()
