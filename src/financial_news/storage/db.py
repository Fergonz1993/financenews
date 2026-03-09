"""Database bootstrap helpers for asynchronous PostgreSQL access."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command
from financial_news.config import get_settings
from financial_news.storage.models import Base


def _coerce_db_url() -> str:
    """Build the async SQLAlchemy URL from typed settings."""
    return get_settings().database.async_url


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_schema_initialized = False
_schema_lock = asyncio.Lock()


def _is_schema_initialized() -> bool:
    return _schema_initialized


def get_engine() -> AsyncEngine:
    """Create or return the cached async engine."""
    global _engine
    if _engine is not None:
        return _engine

    database = get_settings().database
    _engine = create_async_engine(
        database.async_url,
        pool_pre_ping=True,
        echo=database.echo,
    )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create or return cached async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a session with transactional safety."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _run_alembic_upgrade_head() -> None:
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[3] / "alembic"))
    command.upgrade(config, "head")


async def initialize_schema() -> None:
    """Ensure the database schema is initialized once for the process."""
    global _schema_initialized
    if _is_schema_initialized():
        return

    async with _schema_lock:
        if _is_schema_initialized():
            return

        strategy = get_settings().database.bootstrap_strategy
        if strategy == "create_all":
            async with get_engine().begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        else:
            await asyncio.to_thread(_run_alembic_upgrade_head)
        _schema_initialized = True


def get_db_health_check() -> Callable[[], Awaitable[bool]]:
    """Create a small DB health-check callback."""

    async def _check() -> bool:
        try:
            async with get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    return _check
