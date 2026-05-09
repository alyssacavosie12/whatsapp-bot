"""Runtime dependency container installed by the Flask application factory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from flask import Flask, current_app, has_app_context

from core.cache import RedisClientManager
from core.database import DatabasePoolManager
from core.dependency_keys import (
    DATABASE_MANAGER_EXTENSION_KEY,
    REDIS_MANAGER_EXTENSION_KEY,
    RUNTIME_DEPENDENCIES_EXTENSION_KEY,
)

__all__ = [
    "RuntimeDependencies",
    "build_runtime_dependencies",
    "get_runtime_dependencies",
    "install_runtime_dependencies",
]


@dataclass(frozen=True)
class RuntimeDependencies:
    """Runtime services owned by one Flask application instance."""

    database: DatabasePoolManager
    cache: RedisClientManager


def build_runtime_dependencies() -> RuntimeDependencies:
    """Create the default runtime dependency container."""
    return RuntimeDependencies(
        database=DatabasePoolManager(),
        cache=RedisClientManager(),
    )


_DEFAULT_RUNTIME_DEPENDENCIES = build_runtime_dependencies()


def _current_flask_app() -> Flask:
    """Return the concrete Flask app behind LocalProxy ``current_app``."""
    return cast(Flask, cast(Any, current_app)._get_current_object())


def install_runtime_dependencies(
    flask_app: Flask,
    dependencies: RuntimeDependencies | None = None,
) -> RuntimeDependencies:
    """Install runtime dependencies into ``app.extensions``."""
    runtime_dependencies = dependencies or build_runtime_dependencies()
    flask_app.extensions[RUNTIME_DEPENDENCIES_EXTENSION_KEY] = runtime_dependencies
    flask_app.extensions[DATABASE_MANAGER_EXTENSION_KEY] = runtime_dependencies.database
    flask_app.extensions[REDIS_MANAGER_EXTENSION_KEY] = runtime_dependencies.cache
    return runtime_dependencies


def get_runtime_dependencies() -> RuntimeDependencies:
    """Return runtime dependencies for the current Flask app context.

    Without an app context, returns a process-local fallback container. This is
    useful for CLI scripts and tests that need shared pools/managers without
    constructing a Flask app.
    """
    if not has_app_context():
        return _DEFAULT_RUNTIME_DEPENDENCIES

    app = _current_flask_app()
    dependencies = app.extensions.get(RUNTIME_DEPENDENCIES_EXTENSION_KEY)
    if isinstance(dependencies, RuntimeDependencies):
        return dependencies

    return install_runtime_dependencies(app)
