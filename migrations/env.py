"""Alembic environment for the WhatsApp bot.

We don't use SQLAlchemy models in the app — psycopg goes straight to SQL —
so this env file just plumbs the runtime DATABASE_URL into Alembic and lets
each migration script execute the SQL it owns.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool

from settings import INBOX_DATABASE_URL

config = context.config

# Override the placeholder URL from alembic.ini with the real env URL on
# every invocation. Use the psycopg3 driver explicitly so SQLAlchemy picks
# the same driver psycopg-pool already imports for the app.
if INBOX_DATABASE_URL:
    runtime_url = INBOX_DATABASE_URL
    if runtime_url.startswith("postgresql://"):
        runtime_url = "postgresql+psycopg://" + runtime_url[len("postgresql://") :]
    config.set_main_option("sqlalchemy.url", runtime_url)

# No SQLAlchemy ORM in this app — migrations execute raw SQL via op.execute.
target_metadata = None


def run_migrations_offline() -> None:
    """Generate SQL without a live connection (useful for `alembic upgrade --sql`)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against the configured database."""
    section = config.get_section(config.config_ini_section) or {}
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
