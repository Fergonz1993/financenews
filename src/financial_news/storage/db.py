"""Database bootstrap helpers for asynchronous PostgreSQL access."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from financial_news.config import get_settings
from financial_news.storage.models import Base


def _coerce_db_url() -> str:
    """Build the async SQLAlchemy URL from environment settings."""
    app_settings = get_settings()
    raw_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("DB_URL")
        or app_settings.database.url
    )

    if raw_url.startswith("postgresql+asyncpg://"):
        return raw_url
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if "://" not in raw_url:
        return f"postgresql+asyncpg://{raw_url}"
    return raw_url


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Create or return the cached async engine."""
    global _engine
    if _engine is not None:
        return _engine

    database_url = _coerce_db_url()
    _engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
        echo=os.getenv("DB_ECHO", "false").lower() in {"1", "true", "on", "yes"},
    )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create or return cached async session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
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


async def initialize_schema() -> None:
    """Create tables if they do not exist."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_db_health_check() -> Callable[[], AsyncIterator[bool]]:
    """Create a small DB health-check callback."""

    async def _check() -> bool:
        try:
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    return _check
