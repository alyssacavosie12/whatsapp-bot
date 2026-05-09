from __future__ import annotations

from typing import Any, cast

from flask import Flask

from core import cache, database
from core.dependency_keys import (
    DATABASE_MANAGER_EXTENSION_KEY,
    REDIS_MANAGER_EXTENSION_KEY,
    RUNTIME_DEPENDENCIES_EXTENSION_KEY,
)
from core.runtime import install_runtime_dependencies


class _FakeDatabaseManager:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def get_pool(self, database_url: str, *, dict_rows: bool = False) -> str:
        self.calls.append((database_url, dict_rows))
        return "fake-db-pool"


class _FakeRedisManager:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_client(self, url: str) -> str:
        self.calls.append(url)
        return "fake-redis-client"


def test_database_pool_uses_flask_extension_dependency() -> None:
    app = Flask(__name__)
    fake_manager = _FakeDatabaseManager()
    app.extensions[DATABASE_MANAGER_EXTENSION_KEY] = fake_manager

    with app.app_context():
        result = database.get_db_pool("postgresql://example", dict_rows=True)

    assert result == "fake-db-pool"
    assert fake_manager.calls == [("postgresql://example", True)]


def test_redis_client_uses_flask_extension_dependency() -> None:
    app = Flask(__name__)
    fake_manager = _FakeRedisManager()
    app.extensions[REDIS_MANAGER_EXTENSION_KEY] = fake_manager

    with app.app_context():
        result = cast(Any, cache.get_redis("redis://example"))

    assert result == "fake-redis-client"
    assert fake_manager.calls == ["redis://example"]


def test_install_runtime_dependencies_registers_app_extensions() -> None:
    app = Flask(__name__)

    dependencies = install_runtime_dependencies(app)

    assert app.extensions[RUNTIME_DEPENDENCIES_EXTENSION_KEY] is dependencies
    assert app.extensions[DATABASE_MANAGER_EXTENSION_KEY] is dependencies.database
    assert app.extensions[REDIS_MANAGER_EXTENSION_KEY] is dependencies.cache
