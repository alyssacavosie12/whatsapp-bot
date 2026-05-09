"""Shared PostgreSQL connection pools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final, cast

from flask import current_app, has_app_context

from core.dependency_keys import DATABASE_MANAGER_EXTENSION_KEY
from settings import (
    DATABASE_POOL_MAX_SIZE,
    DATABASE_POOL_MAX_WAITING,
    DATABASE_POOL_MIN_SIZE,
    DATABASE_POOL_TIMEOUT_SECONDS,
)


class DatabasePoolUnavailable(RuntimeError):
    """Raised when the PostgreSQL connection pool cannot be initialized."""


_PSYCOPG_ERROR_TYPE: type[BaseException]
try:
    from psycopg import Error as _ImportedPsycopgError
except ImportError:
    _PSYCOPG_ERROR_TYPE = DatabasePoolUnavailable
else:
    _PSYCOPG_ERROR_TYPE = _ImportedPsycopgError

_POOL_TIMEOUT_TYPE: type[BaseException]
try:
    from psycopg_pool import PoolTimeout as _ImportedPoolTimeout
except ImportError:
    _POOL_TIMEOUT_TYPE = DatabasePoolUnavailable
else:
    _POOL_TIMEOUT_TYPE = _ImportedPoolTimeout

DATABASE_OPERATION_ERRORS: Final[tuple[type[BaseException], ...]] = (
    DatabasePoolUnavailable,
    _PSYCOPG_ERROR_TYPE,
    _POOL_TIMEOUT_TYPE,
    ConnectionError,
    OSError,
    TimeoutError,
    TypeError,
    ValueError,
)


@dataclass(frozen=True)
class DatabasePoolSettings:
    """Configuration for shared PostgreSQL connection pools."""

    min_size: int = DATABASE_POOL_MIN_SIZE
    max_size: int = DATABASE_POOL_MAX_SIZE
    timeout_seconds: float = DATABASE_POOL_TIMEOUT_SECONDS
    max_waiting: int = DATABASE_POOL_MAX_WAITING


@dataclass
class DatabasePoolManager:
    """Own PostgreSQL connection pools for one application runtime."""

    settings: DatabasePoolSettings = field(default_factory=DatabasePoolSettings)
    _pools: dict[tuple[str, bool], Any] = field(default_factory=dict)

    def get_pool(self, database_url: str, *, dict_rows: bool = False) -> Any:
        """Return a shared psycopg3 connection pool."""
        if not database_url:
            raise DatabasePoolUnavailable("DATABASE_URL is not configured")

        key = (database_url, dict_rows)
        pool = self._pools.get(key)
        if pool is not None:
            return pool

        try:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
        except ImportError as exc:
            raise DatabasePoolUnavailable("psycopg_pool is required") from exc

        kwargs: dict[str, Any] = {"autocommit": True, "connect_timeout": 5}
        if dict_rows:
            kwargs["row_factory"] = dict_row

        max_size = max(1, self.settings.max_size)
        min_size = max(0, min(self.settings.min_size, max_size))
        pool = ConnectionPool(
            conninfo=database_url,
            min_size=min_size,
            max_size=max_size,
            timeout=self.settings.timeout_seconds,
            max_waiting=max(1, self.settings.max_waiting),
            kwargs=kwargs,
        )
        self._pools[key] = pool
        return pool

    def initialize_pool(self, database_url: str, *, dict_rows: bool = False) -> None:
        """Create a pool eagerly for application startup."""
        self.get_pool(database_url, dict_rows=dict_rows)

    def connect(self, database_url: str, *, dict_rows: bool = False) -> Any:
        """Return a pooled connection context manager."""
        return self.get_pool(database_url, dict_rows=dict_rows).connection()

    def close(self) -> None:
        """Close all initialized PostgreSQL pools."""
        for pool in self._pools.values():
            pool.close()

        self._pools.clear()


_DEFAULT_DATABASE_MANAGER = DatabasePoolManager()


def _current_database_manager() -> DatabasePoolManager:
    """Return the app-injected database manager or the CLI fallback."""
    if has_app_context():
        app = cast(Any, current_app)._get_current_object()
        manager = app.extensions.get(DATABASE_MANAGER_EXTENSION_KEY)
        if manager is not None:
            return cast(DatabasePoolManager, manager)

    return _DEFAULT_DATABASE_MANAGER


def get_db_pool(database_url: str, *, dict_rows: bool = False) -> Any:
    """Return a shared psycopg3 connection pool.

    Args:
        database_url: PostgreSQL connection URL.
        dict_rows: When true, rows are returned as dictionaries.
    """
    return _current_database_manager().get_pool(database_url, dict_rows=dict_rows)


def initialize_db_pool(database_url: str, *, dict_rows: bool = False) -> None:
    """Create the shared pool for application startup.

    Args:
        database_url: PostgreSQL connection URL.
        dict_rows: When true, initialize the dictionary-row pool.
    """
    _current_database_manager().initialize_pool(database_url, dict_rows=dict_rows)


def connect(database_url: str, *, dict_rows: bool = False) -> Any:
    """Return a pooled connection context manager.

    Args:
        database_url: PostgreSQL connection URL.
        dict_rows: When true, rows are returned as dictionaries.
    """
    return _current_database_manager().connect(database_url, dict_rows=dict_rows)


def close_db_pools() -> None:
    """Close all initialized PostgreSQL pools."""
    _current_database_manager().close()
