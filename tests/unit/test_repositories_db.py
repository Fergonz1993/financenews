"""Database-backed repository tests for critical storage paths."""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from financial_news.storage.db import _coerce_db_url
from financial_news.storage.repositories import (
    ArticleRepository,
    IngestionRunRepository,
    IngestionStateRepository,
    SourceConfig,
    SourceRepository,
    UserArticleStateRepository,
)


def _require_database_url() -> str:
    raw = os.getenv("DATABASE_URL")
    if not raw:
        pytest.skip("DATABASE_URL is required for repository DB tests")
    return _coerce_db_url()


def _migrate_database(db_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    migrated = subprocess.run(
        ["alembic", "upgrade", "head"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if migrated.returncode != 0:
        message = (migrated.stderr or migrated.stdout or "alembic upgrade failed").strip()
        pytest.skip(f"Unable to migrate test database: {message[:500]}")


@pytest_asyncio.fixture
async def session_factory() -> object:
    db_url = _require_database_url()
    _migrate_database(db_url)

    engine = create_async_engine(
        db_url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "TRUNCATE TABLE "
                    "user_saved_articles, article_dedupe, articles, ingestion_state, ingestion_runs, sources "
                    "RESTART IDENTITY CASCADE"
                )
            )

        yield async_sessionmaker(bind=engine, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_source_repository_lifecycle(session_factory: object) -> None:
    repo = SourceRepository(session_factory=session_factory)

    upserted = await repo.upsert_sources(
        [
            SourceConfig(
                source_key="reuters",
                name="Reuters",
                url="https://www.reuters.com/markets",
                source_type="rss",
                source_category="news",
                connector_type="rss",
                enabled=True,
            ),
            SourceConfig(
                source_key="sec-edgar",
                name="SEC EDGAR",
                url="https://www.sec.gov/news",
                source_type="sec",
                source_category="regulatory",
                connector_type="sec",
                enabled=True,
            ),
        ]
    )

    assert len(upserted) == 2
    assert {item.source_key for item in upserted} == {"reuters", "sec-edgar"}

    source_map = await repo.list_source_map(enabled_only=False)
    assert "reuters" in source_map
    assert "sec-edgar" in source_map

    reuters = await repo.get_by_key("reuters")
    assert reuters is not None

    by_identifier = await repo.get_by_identifier(str(reuters.id))
    assert by_identifier is not None
    assert by_identifier.source_key == "reuters"

    updated = await repo.set_enabled(reuters.id, False)
    assert updated is not None
    assert updated.enabled is False

    enabled_sources = await repo.list_sources(enabled_only=True)
    assert {src.source_key for src in enabled_sources} == {"sec-edgar"}

    deleted = await repo.delete("reuters")
    assert deleted is True
    assert await repo.get_by_key("reuters") is None


@pytest.mark.asyncio
async def test_article_repository_upsert_dedupe_and_query(session_factory: object) -> None:
    source_repo = SourceRepository(session_factory=session_factory)
    article_repo = ArticleRepository(session_factory=session_factory)

    sources = await source_repo.upsert_sources(
        [
            SourceConfig(
                source_key="marketwatch",
                name="MarketWatch",
                url="https://feeds.marketwatch.com/marketwatch/topstories/",
                source_type="rss",
                enabled=True,
            )
        ]
    )
    source = sources[0]

    stored = await article_repo.upsert_deduplicated(
        run_id="run-1",
        items=[
            {
                "id": "article-1",
                "source_id": source.id,
                "source": "MarketWatch",
                "title": "Fed Signals Rate Pause",
                "url": "https://www.marketwatch.com/story/fed-signals-rate-pause?utm_source=news",
                "published_at": "2026-03-01T10:00:00Z",
                "content": "Federal Reserve commentary for markets.",
                "sentiment": "neutral",
                "sentiment_score": 0.5,
                "market_impact_score": 0.7,
                "topics": ["Policy", "Markets"],
                "key_entities": ["Federal Reserve"],
            },
            {
                "id": "article-2",
                "source_id": source.id,
                "source": "MarketWatch",
                "title": "Fed Signals Rate Pause",
                "url": "https://www.marketwatch.com/story/fed-signals-rate-pause",
                "published_at": "2026-03-01T10:00:00Z",
                "content": "Duplicate URL variant should dedupe.",
                "sentiment": "neutral",
                "topics": ["Policy"],
                "key_entities": ["Federal Reserve"],
            },
        ],
    )

    assert stored.items_seen == 2
    assert stored.items_stored == 1
    assert stored.items_skipped == 1

    api_rows = await article_repo.list_for_api(
        source="marketwatch",
        search="federal reserve",
        topic="policy",
        sort_by="relevance",
        sort_order="desc",
        limit=10,
    )
    assert len(api_rows) == 1
    assert api_rows[0]["title"] == "Fed Signals Rate Pause"

    total = await article_repo.count_for_api(source="marketwatch", search="federal")
    assert total == 1

    source_names = await article_repo.get_sources_from_articles()
    topics = await article_repo.get_topics_from_articles()
    assert source_names == ["MarketWatch"]
    assert set(topics) == {"Markets", "Policy"}

    article = await article_repo.get_by_id("article-1")
    assert article is not None


@pytest.mark.asyncio
async def test_ingestion_run_and_state_repositories(session_factory: object) -> None:
    source_repo = SourceRepository(session_factory=session_factory)
    run_repo = IngestionRunRepository(session_factory=session_factory)
    state_repo = IngestionStateRepository(session_factory=session_factory)

    source = (
        await source_repo.upsert_sources(
            [
                SourceConfig(
                    source_key="bbc-business",
                    name="BBC Business",
                    url="https://feeds.bbci.co.uk/news/business/rss.xml",
                    source_type="rss",
                    enabled=True,
                )
            ]
        )
    )[0]

    await run_repo.create_run("run-xyz", requested_sources=1)
    await run_repo.update("run-xyz", status="running", items_seen=3)
    await run_repo.finish_run(
        "run-xyz",
        items_seen=3,
        items_stored=2,
        items_skipped=1,
        failed_sources=0,
        source_errors=0,
        error_summary=[],
        source_results=[{"source_key": source.source_key, "status": "stored"}],
        status="completed",
    )

    run = await run_repo.get("run-xyz")
    assert run is not None
    assert run.status == "completed"
    assert run.items_stored == 2

    state = await state_repo.ensure_state(source.id)
    assert state.source_id == source.id

    await state_repo.mark_source_failure(
        source.id,
        error="timeout",
        cursor_type="published_at",
        cursor_value="2026-03-01T10:00:00+00:00",
        latency_ms=450,
        base_delay_seconds=10,
        max_delay_seconds=60,
        jitter_ms=0,
    )

    failed_state = await state_repo.get_for_source(source.id)
    assert failed_state is not None
    assert failed_state.disabled_by_failure is True
    assert failed_state.consecutive_failures == 1
    assert failed_state.last_error == "timeout"
    assert failed_state.next_retry_at is not None

    await state_repo.mark_source_success(
        source.id,
        cursor_type="published_at",
        cursor_value="2026-03-01T12:00:00+00:00",
        last_published_at=datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
        latency_ms=120,
        etag='W/"etag-1"',
    )

    success_state = await state_repo.get_for_source(source.id)
    assert success_state is not None
    assert success_state.disabled_by_failure is False
    assert success_state.consecutive_failures == 0
    assert success_state.last_error is None
    assert success_state.etag == 'W/"etag-1"'

    all_states = await state_repo.get_all()
    assert len(all_states) == 1


@pytest.mark.asyncio
async def test_user_article_state_repository_flow(session_factory: object) -> None:
    source_repo = SourceRepository(session_factory=session_factory)
    article_repo = ArticleRepository(session_factory=session_factory)
    user_repo = UserArticleStateRepository(session_factory=session_factory)

    source = (
        await source_repo.upsert_sources(
            [
                SourceConfig(
                    source_key="yahoo-finance",
                    name="Yahoo Finance",
                    url="https://finance.yahoo.com/news/rssindex",
                    source_type="rss",
                    enabled=True,
                )
            ]
        )
    )[0]

    await article_repo.upsert_deduplicated(
        run_id="run-user",
        items=[
            {
                "id": "article-user-1",
                "source_id": source.id,
                "source": "Yahoo Finance",
                "title": "Tech Stocks Rally",
                "url": "https://finance.yahoo.com/news/tech-stocks-rally",
                "published_at": "2026-03-01T15:00:00Z",
                "content": "Technology equities rallied in late trading.",
                "topics": ["Markets"],
                "key_entities": ["NASDAQ"],
            }
        ],
    )

    snapshot = {
        "id": "article-user-1",
        "title": "Tech Stocks Rally",
        "source": "Yahoo Finance",
    }

    await user_repo.save_article(
        user_id="user-1",
        article_id="article-user-1",
        snapshot=snapshot,
    )
    assert await user_repo.is_saved("user-1", "article-user-1") is True

    saved = await user_repo.list_saved("user-1")
    assert len(saved) == 1
    assert saved[0]["id"] == "article-user-1"
    assert saved[0]["title"] == "Tech Stocks Rally"
    assert "saved_at" in saved[0]

    removed = await user_repo.unsave_article("user-1", "article-user-1")
    assert removed is True
    assert await user_repo.is_saved("user-1", "article-user-1") is False
