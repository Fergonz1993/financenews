from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from financial_news.storage.db import _coerce_db_url
from financial_news.storage.models import Base


config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)


def _database_url() -> str:
    raw_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("DB_URL")
        or _coerce_db_url()
    )
    if raw_url.startswith("postgresql+asyncpg://"):
        return raw_url
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw_url


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        render_as_batch=False,
    )

    with context.begin_transaction():
        context.run_migrations()


def _run_sync_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    db_url = _database_url()
    connectable = create_async_engine(
        db_url,
        poolclass=pool.NullPool,
    )

    async def run_async() -> None:
        async with connectable.connect() as connection:
            await connection.run_sync(_run_sync_migrations)
        await connectable.dispose()

    asyncio.run(run_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
