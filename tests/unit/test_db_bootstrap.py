"""Tests for async database bootstrap helpers."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import financial_news.storage.db as db
from financial_news.storage.models import Base


@pytest.fixture(autouse=True)
def _reset_db_bootstrap_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "_schema_initialized", False)
    monkeypatch.setattr(db, "_schema_lock", asyncio.Lock())


@pytest.mark.asyncio
async def test_initialize_schema_uses_create_all_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_sync_calls: list[object] = []

    class _FakeConnection:
        async def run_sync(self, fn):
            run_sync_calls.append(fn)

    class _FakeBegin:
        async def __aenter__(self):
            return _FakeConnection()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class _FakeEngine:
        def begin(self):
            return _FakeBegin()

    monkeypatch.setattr(
        db,
        "get_settings",
        lambda: SimpleNamespace(
            database=SimpleNamespace(bootstrap_strategy="create_all")
        ),
    )
    monkeypatch.setattr(db, "get_engine", lambda: _FakeEngine())

    await db.initialize_schema()
    await db.initialize_schema()

    assert run_sync_calls == [Base.metadata.create_all]


@pytest.mark.asyncio
async def test_initialize_schema_runs_alembic_upgrade_for_migrate_strategy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    to_thread = AsyncMock(return_value=None)
    monkeypatch.setattr(
        db,
        "get_settings",
        lambda: SimpleNamespace(
            database=SimpleNamespace(bootstrap_strategy="migrate")
        ),
    )
    monkeypatch.setattr(db.asyncio, "to_thread", to_thread)

    await db.initialize_schema()

    to_thread.assert_awaited_once_with(db._run_alembic_upgrade_head)


@pytest.mark.asyncio
async def test_initialize_schema_skips_bootstrap_after_first_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    to_thread = AsyncMock(return_value=None)
    monkeypatch.setattr(
        db,
        "get_settings",
        lambda: SimpleNamespace(
            database=SimpleNamespace(bootstrap_strategy="migrate")
        ),
    )
    monkeypatch.setattr(db.asyncio, "to_thread", to_thread)

    await db.initialize_schema()
    await db.initialize_schema()

    to_thread.assert_awaited_once_with(db._run_alembic_upgrade_head)
