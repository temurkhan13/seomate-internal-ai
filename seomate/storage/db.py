"""Database engine and session management.

Two engines exist side by side:

- ``get_async_engine()`` is used by the auditor runtime (orchestrator,
  extractors, repository writes) and by the API (read endpoints).
- ``get_sync_engine()`` is used by Alembic for schema migrations only.

Both point at the same Postgres instance. URL is built either from the
``DATABASE_URL`` env var (preferred) or composed from individual
``POSTGRES_*`` env vars as a fallback.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class DatabaseSettings(BaseSettings):
    """Read DATABASE_URL or compose one from individual components."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    DATABASE_URL: str | None = None
    POSTGRES_USER: str = "seomate"
    POSTGRES_PASSWORD: str = "seomate_dev"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_DB: str = "seomate"

    @property
    def sqlalchemy_url(self) -> str:
        """Return a psycopg3-compatible SQLAlchemy URL string."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)


@lru_cache(maxsize=1)
def get_settings() -> DatabaseSettings:
    """Return cached DatabaseSettings instance."""
    return DatabaseSettings()


@lru_cache(maxsize=1)
def get_async_engine() -> AsyncEngine:
    """Async engine for the auditor runtime and the API."""
    return create_async_engine(
        get_settings().sqlalchemy_url,
        echo=False,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_sync_engine() -> Engine:
    """Sync engine, used by Alembic only.

    Alembic does not run async migrations cleanly out of the box; using
    a sync engine for migrations is the simplest and most reliable
    pattern. The same Postgres instance is reached via both engines.
    """
    return create_engine(
        get_settings().sqlalchemy_url,
        echo=False,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_async_engine(),
        expire_on_commit=False,
    )


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Async session context manager with automatic commit/rollback."""
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
