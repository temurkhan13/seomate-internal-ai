"""Alembic migration environment for SEOMATE.

Sync mode by design: Alembic on the sync engine is the simplest and most
reliable pattern. The same Postgres instance is reached by the auditor's
async runtime and by Alembic; they just use different SQLAlchemy engines.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

# Import models so Base.metadata knows about every table.
from seomate.storage.db import get_settings
from seomate.storage.models import Base

# Standard Alembic config
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the SQLAlchemy URL at runtime from our settings rather than
# embedding it in alembic.ini.
config.set_main_option("sqlalchemy.url", get_settings().sqlalchemy_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a DB connection)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (against the live DB)."""
    connectable = create_engine(config.get_main_option("sqlalchemy.url"))
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
