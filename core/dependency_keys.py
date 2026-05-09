"""Flask extension keys for runtime dependency injection."""

from __future__ import annotations

from typing import Final

DATABASE_MANAGER_EXTENSION_KEY: Final = "tulum_btx.database_manager"
MESSAGE_PROCESSOR_DEPENDENCIES_EXTENSION_KEY: Final = "tulum_btx.message_processor_dependencies"
REDIS_MANAGER_EXTENSION_KEY: Final = "tulum_btx.redis_manager"
RUNTIME_DEPENDENCIES_EXTENSION_KEY: Final = "tulum_btx.runtime_dependencies"
