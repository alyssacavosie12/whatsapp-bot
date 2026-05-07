"""Shared PostgreSQL connection pools."""

from __future__ import annotations

from typing import Any

from settings import (
    DATABASE_POOL_MAX_SIZE,
    DATABASE_POOL_MAX_WAITING,
    DATABASE_POOL_MIN_SIZE,
    DATABASE_POOL_TIMEOUT_SECONDS,
)

_DB_POOLS: dict[tuple[str, bool], Any] = {}


class DatabasePoolUnavailable(RuntimeError):
    """Raised when the PostgreSQL connection pool cannot be initialized."""


def get_db_pool(database_url: str, *, dict_rows: bool = False) -> Any:
    """Return a shared psycopg3 connection pool.

    Args:
        database_url: PostgreSQL connection URL.
        dict_rows: When true, rows are returned as dictionaries.
    """
    if not database_url:
        raise DatabasePoolUnavailable("DATABASE_URL is not configured")

    key = (database_url, dict_rows)
    pool = _DB_POOLS.get(key)
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

    max_size = max(1, DATABASE_POOL_MAX_SIZE)
    min_size = max(0, min(DATABASE_POOL_MIN_SIZE, max_size))
    pool = ConnectionPool(
        conninfo=database_url,
        min_size=min_size,
        max_size=max_size,
        timeout=DATABASE_POOL_TIMEOUT_SECONDS,
        max_waiting=max(1, DATABASE_POOL_MAX_WAITING),
        kwargs=kwargs,
    )
    _DB_POOLS[key] = pool
    return pool


def initialize_db_pool(database_url: str, *, dict_rows: bool = False) -> None:
    """Create the shared pool for application startup.

    Args:
        database_url: PostgreSQL connection URL.
        dict_rows: When true, initialize the dictionary-row pool.
    """
    get_db_pool(database_url, dict_rows=dict_rows)


def connect(database_url: str, *, dict_rows: bool = False) -> Any:
    """Return a pooled connection context manager.

    Args:
        database_url: PostgreSQL connection URL.
        dict_rows: When true, rows are returned as dictionaries.
    """
    return get_db_pool(database_url, dict_rows=dict_rows).connection()


def close_db_pools() -> None:
    """Close all initialized PostgreSQL pools."""
    for pool in _DB_POOLS.values():
        pool.close()

    _DB_POOLS.clear()
