#!/usr/bin/env python3
"""Stage-1 ingestion tests for production-readiness foundation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

import financial_news.services.news_ingest as news_ingest
from financial_news.core.schemas import ParsedArticle
from financial_news.services.news_ingest import NewsIngestor, SourceResult
from financial_news.storage.repositories import IngestResult


def test_feed_env_parsing_and_dedup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "NEWS_INGEST_FEEDS",
        "https://example.com/feed, https://example.com/feed , https://another.com/rss",
    )
    monkeypatch.setenv("SEC_PRESS_RELEASE_FEEDS", "https://www.sec.gov/news/pressreleases.rss")

    feeds = news_ingest._env_or_default_sources()
    urls = [url for _name, url in feeds]

    assert "https://www.sec.gov/news/pressreleases.rss" in urls
    assert urls.count("https://example.com/feed") == 1
    assert "https://another.com/rss" in urls


def test_infer_source_metadata_for_regulatory_feed() -> None:
    metadata = news_ingest._infer_source_metadata(
        source_name="SEC Press Releases",
        source_url="https://www.sec.gov/news/pressreleases.rss",
        source_type="sec",
    )
    assert metadata["source_category"] == "regulatory"
    assert metadata["connector_type"] == "sec"
    assert metadata["requires_user_agent"] is True
    assert metadata["legal_basis"] == "public_regulatory_disclosure"
    assert metadata["rate_profile"] == "sec-conservative"


def test_build_source_url_and_hash_helpers() -> None:
    source_url = "https://api.example.com/feed?topic=markets"
    rebuilt = news_ingest._build_source_url(
        source_url,
        supports_since=True,
        cursor_value="2026-02-28T12:00:00+00:00",
    )
    assert "topic=markets" in rebuilt
    assert "from=2026-02-28T12%3A00%3A00%2B00%3A00" in rebuilt

    unchanged = news_ingest._build_source_url(
        source_url,
        supports_since=False,
        cursor_value="2026-02-28T12:00:00+00:00",
    )
    assert unchanged == source_url

    normalized = news_ingest._normalize_source_url(
        "https://api.example.com/feed?topic=markets&x=1"
    )
    assert normalized == "https://api.example.com/feed"

    item_id, url_hash, dedupe_key = news_ingest._dedupe_hashes(None, "u1", "d1")
    assert item_id
    assert url_hash == "u1"
    assert dedupe_key == "d1"


def test_dedupe_keys_stable_for_duplicate_payloads() -> None:
    """Stable dedupe for canonical URL variants that differ in case/params."""
    item_a = {
        "title": "Federal Reserve Signals Rate Hikes",
        "published_at": "2025-02-20T10:00:00Z",
        "source": "Reuters",
        "url": "https://www.reuters.com/path/article?utm_source=mail&v=1#section",
        "content": "The Federal Reserve met today.",
    }
    item_b = {
        "title": "Federal Reserve Signals Rate Hikes",
        "published_at": "2025-02-20T10:00:00Z",
        "source": "reuters",
        "url": "https://WWW.REUTERS.COM/path/article?v=1&utm_campaign=weekly",
        "content": "Different summary text.",
    }

    normalized_a = news_ingest.ArticleRepository._normalize_for_db(item_a)
    normalized_b = news_ingest.ArticleRepository._normalize_for_db(item_b)

    assert normalized_a is not None
    assert normalized_b is not None
    assert normalized_a["url_hash"] == normalized_b["url_hash"]
    assert normalized_a["dedupe_key"] == normalized_b["dedupe_key"]


def test_dedupe_keys_block_cross_source_duplicates() -> None:
    """Stable dedupe for identical titles published by different sources on the same day."""
    original = {
        "title": "Fed rate cut brings confidence",
        "published_at": "2025-02-20T10:00:00Z",
        "source": "CNBC",
        "url": "https://cnbc.com/news/123",
        "content": "Original wire content.",
    }
    syndicated = {
        "title": "fed rate CUT brings confidence  ",
        "published_at": "2025-02-20T23:59:59Z",  # later same day
        "source": "Yahoo Finance",
        "url": "https://finance.yahoo.com/news/123", # completely different url
        "content": "Syndicated piece.",
    }

    normalized_orig = news_ingest.ArticleRepository._normalize_for_db(original)
    normalized_synd = news_ingest.ArticleRepository._normalize_for_db(syndicated)

    assert normalized_orig is not None
    assert normalized_synd is not None
    assert normalized_orig["url_hash"] != normalized_synd["url_hash"]
    assert normalized_orig["dedupe_key"] == normalized_synd["dedupe_key"]


def test_dedupe_keys_stable_for_title_spacing_and_case_with_missing_url() -> None:
    """Title normalization should remove casing and spacing noise when URL is missing."""
    first = {
        "title": "  AI   Index  Up  4.2% ",
        "published_at": "2025-02-20T11:00:00Z",
        "source": "CNBC",
        "url": "   ",
        "content": "Markets rose after AI index release.",
    }
    duplicate = {
        "title": "AI Index up 4.2%",
        "published_at": "2025-02-20T11:00:00Z",
        "source": " cnbc ",
        "url": "",
        "content": "Markets rose after AI index release.",
    }

    normalized_first = news_ingest.ArticleRepository._normalize_for_db(first)
    normalized_duplicate = news_ingest.ArticleRepository._normalize_for_db(duplicate)

    assert normalized_first is not None
    assert normalized_duplicate is not None
    assert normalized_first["url_hash"] == normalized_duplicate["url_hash"]
    assert normalized_first["dedupe_key"] == normalized_duplicate["dedupe_key"]


def test_extract_entities_ignores_script_noise_tokens() -> None:
    text = (
        "Supreme Court strikes down tariffs. "
        "AfY8Hf Dftppe DpimGf and EP1ykd should not appear as entities."
    )

    entities = news_ingest._extract_entities(text)

    assert "Supreme Court" in entities
    assert "AfY8Hf" not in entities
    assert "Dftppe" not in entities
    assert "DpimGf" not in entities
    assert "EP1ykd" not in entities


@pytest.mark.asyncio
async def test_entry_to_record_skips_full_text_fetch_for_google_news_wrapper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    async def fake_fetch_entry_full_text(*, session: Any, source_url: str, max_full_text_chars: int) -> str:
        nonlocal called
        called = True
        return "This should not be used."

    monkeypatch.setattr(news_ingest, "_fetch_entry_full_text", fake_fetch_entry_full_text)

    record = await news_ingest._entry_to_record(
        "Google News Finance",
        {
            "title": "Markets React to Rate Decision",
            "link": "https://news.google.com/rss/articles/CBMiExample?oc=5",
            "summary": "Stocks rose after the announcement.",
            "published": "2026-02-25T10:00:00+00:00",
        },
        session=SimpleNamespace(),
        fetch_full_text=True,
        min_full_text_chars=240,
        max_full_text_chars=5000,
    )

    assert record is not None
    assert called is False
    assert record.content == "Stocks rose after the announcement."


@pytest.mark.asyncio
async def test_fetch_and_parse_source_filters_by_published_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    source = SimpleNamespace(
        id=1,
        name="Source One",
        url="https://example.com/feed",
        source_type="rss",
    )
    state = SimpleNamespace(
        cursor_value="2025-02-20T10:00:00+00:00",
    )

    async def fake_entry_to_record(
        *,
        source_name: str,
        entry: dict[str, Any],
        **kwargs: Any,
    ) -> ParsedArticle:
        return ParsedArticle(
            id=entry["id"],
            source_name=source_name,
            title=entry["title"],
            url=entry["link"],
            content=entry.get("content", ""),
            published_at=datetime.fromisoformat(entry["published"]),
        )

    async def fake_fetch_feed(
        session: Any,
        source_url: str,
        source_name: str,
        max_entries: int,
    ) -> tuple[list[dict[str, Any]], str | None]:
        assert source_url == "https://example.com/feed"
        assert source_name == "Source One"
        assert max_entries == 25
        return (
            [
                {
                    "id": "old",
                    "title": "Old Item",
                    "published": "2025-02-20T09:00:00+00:00",
                    "link": "https://example.com/old",
                },
                {
                    "id": "new",
                    "title": "New Item",
                    "published": "2025-02-20T12:00:00+00:00",
                    "link": "https://example.com/new",
                },
            ],
            'W/"123"',
        )

    monkeypatch.setattr(news_ingest, "_entry_to_record", fake_entry_to_record)
    monkeypatch.setattr(news_ingest, "_fetch_feed", fake_fetch_feed)

    ingestor = NewsIngestor.__new__(NewsIngestor)
    ingestor._max_items_per_source = 25
    ingestor._enable_full_text_fetch = False
    ingestor._min_entry_content_chars = 240
    ingestor._full_text_max_chars = 5000

    parsed, etag = await ingestor._fetch_and_parse_source(
        session=SimpleNamespace(),
        source=source,
        state=state,
        parser_contract={},
    )

    assert etag == 'W/"123"'
    assert len(parsed) == 1
    assert parsed[0].id == "new"
    assert parsed[0].title == "New Item"


@pytest.mark.asyncio
async def test_fetch_and_parse_source_adds_since_query_for_supported_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    source = SimpleNamespace(
        id=1,
        name="SEC Source",
        url="https://www.sec.gov/api?category=news",
        source_type="sec",
    )
    state = SimpleNamespace(
        cursor_value="2025-02-20T10:00:00+00:00",
    )
    captured: dict[str, str] = {}

    async def fake_entry_to_record(
        *,
        source_name: str,
        entry: dict[str, Any],
        **kwargs: Any,
    ) -> ParsedArticle:
        return ParsedArticle(
            id=entry["id"],
            source_name=source_name,
            title=entry["title"],
            url=entry["link"],
            content=entry.get("content", ""),
            published_at=datetime.fromisoformat(entry["published"]),
        )

    async def fake_fetch_feed(
        session: Any,
        source_url: str,
        source_name: str,
        max_entries: int,
    ) -> tuple[list[dict[str, Any]], str | None]:
        captured["source_url"] = source_url
        return (
            [
                {
                    "id": "new",
                    "title": "New SEC Filing",
                    "published": "2025-02-20T11:00:00+00:00",
                    "link": "https://www.sec.gov/123",
                },
            ],
            "etag-value",
        )

    monkeypatch.setattr(news_ingest, "_entry_to_record", fake_entry_to_record)
    monkeypatch.setattr(news_ingest, "_fetch_feed", fake_fetch_feed)

    ingestor = NewsIngestor.__new__(NewsIngestor)
    ingestor._max_items_per_source = 25
    ingestor._enable_full_text_fetch = False
    ingestor._min_entry_content_chars = 240
    ingestor._full_text_max_chars = 5000

    parsed, _ = await ingestor._fetch_and_parse_source(
        session=SimpleNamespace(),
        source=source,
        state=state,
        parser_contract={"supports_since": True, "since_param": "from"},
    )

    assert "from=2025-02-20T10%3A00%3A00%2B00%3A00" in captured["source_url"]
    assert captured["source_url"].startswith("https://www.sec.gov/api")
    assert len(parsed) == 1
    assert parsed[0].source_name == "SEC Source"


@dataclass
class _FakeSource:
    id: int
    name: str
    enabled: bool = True
    source_type: str = "rss"
    source_category: str | None = "news"
    connector_type: str | None = "rss"
    terms_url: str | None = None
    legal_basis: str | None = "public_web_feed"
    provider_domain: str | None = "example.com"
    rate_profile: str | None = "standard"
    requires_api_key: bool = False
    requires_user_agent: bool = False
    user_agent: str | None = None
    retry_policy_json: dict[str, Any] | None = None
    parser_contract_json: dict[str, Any] | None = None
    source_key: str | None = None
    url: str = "https://example.com"

    def __post_init__(self) -> None:
        if self.source_key is None:
            self.source_key = self.name.lower().replace(" ", "-")


@dataclass
class _State:
    source_id: int | None = None
    cursor_type: str | None = None
    cursor_value: str | None = None
    etag: str | None = None
    disabled_by_failure: bool = False
    next_retry_at: datetime | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    last_latency_ms: int | None = None


class _FakeStateRepo:
    def __init__(self, states: list[_State] | dict[int, _State] | None = None) -> None:
        if isinstance(states, dict):
            self.states = {}
            for source_id, state in states.items():
                state.source_id = source_id
                self.states[source_id] = state
        else:
            self.states = {}
            for index, state in enumerate(states or [], start=1):
                state.source_id = index
                self.states[index] = state
        self.success_updates: list[tuple[int, dict[str, Any]]] = []
        self.failure_updates: list[tuple[int, dict[str, Any]]] = []

    async def get_all(self) -> list[_State]:
        return list(self.states.values())

    async def get_for_source(self, source_id: int) -> _State | None:
        return self.states.get(source_id)

    async def mark_source_success(self, source_id: int, **kwargs: Any) -> None:
        self.success_updates.append((source_id, kwargs))

    async def mark_source_failure(self, source_id: int, **kwargs: Any) -> None:
        self.failure_updates.append((source_id, kwargs))


class _FakeArticleRepo:
    def __init__(self, dedup_result: IngestResult) -> None:
        self.result = dedup_result
        self.calls: list[tuple[str, list[dict[str, Any]]]] = []

    async def upsert_deduplicated(self, *, run_id: str, items: list[dict[str, Any]]) -> IngestResult:
        self.calls.append((run_id, items))
        return self.result


class _FakeSourceRepo:
    def __init__(self, sources: list[_FakeSource]) -> None:
        self.sources = sources

    async def upsert_sources(self, sources: list[Any]) -> list[_FakeSource]:
        return self.sources

    async def list_sources(
        self,
        enabled_only: bool = False,
        source_category: str | None = None,
        connector_type: str | None = None,
    ) -> list[_FakeSource]:
        if enabled_only:
            filtered = [source for source in self.sources if source.enabled]
        else:
            filtered = list(self.sources)
        if source_category:
            filtered = [source for source in filtered if source.source_category == source_category]
        if connector_type:
            filtered = [source for source in filtered if source.connector_type == connector_type]
        return filtered


class _FakeRunRepo:
    def __init__(self) -> None:
        self.created: list[tuple[str, int]] = []
        self.finished: list[tuple[str, dict[str, Any]]] = []

    async def create_run(self, run_id: str, requested_sources: int) -> None:
        self.created.append((run_id, requested_sources))

    async def finish_run(self, run_id: str, **fields: Any) -> None:
        self.finished.append((run_id, fields))


def _build_ingestor_for_unit(
    *,
    article_repo: _FakeArticleRepo | None = None,
    state_repo: _FakeStateRepo | None = None,
    source_repo: _FakeSourceRepo | None = None,
    run_repo: _FakeRunRepo | None = None,
) -> NewsIngestor:
    ingestor = NewsIngestor.__new__(NewsIngestor)
    ingestor._article_repo = article_repo or _FakeArticleRepo(IngestResult())
    ingestor._state_repo = state_repo or _FakeStateRepo([])
    ingestor._source_repo = source_repo or _FakeSourceRepo([])
    ingestor._run_repo = run_repo or _FakeRunRepo()
    ingestor._run_lock = asyncio.Lock()  # type: ignore[attr-defined]
    ingestor._run_tasks = {}
    ingestor._max_items_per_source = 25
    ingestor._request_timeout_seconds = 15
    ingestor._min_entry_content_chars = 240
    ingestor._full_text_max_chars = 5000
    ingestor._enable_full_text_fetch = False
    ingestor._dual_write_legacy = False
    return ingestor


def test_build_default_source_configs_includes_connector_metadata() -> None:
    ingestor = _build_ingestor_for_unit()
    configs = ingestor._build_default_source_configs()
    assert configs

    first_rss = next((item for item in configs if item.source_type == "rss"), None)
    assert first_rss is not None
    assert first_rss.source_category in {"news", "aggregator", "research", "policy"}
    assert first_rss.connector_type in {"rss", "sec"}
    assert first_rss.provider_domain is not None
    assert first_rss.legal_basis is not None

    sec_config = next((item for item in configs if item.source_type == "sec"), None)
    assert sec_config is not None
    assert sec_config.requires_user_agent is True
    assert sec_config.rate_profile == "sec-conservative"


@pytest.mark.asyncio
async def test_run_source_keeps_cursor_when_no_new_items(monkeypatch: pytest.MonkeyPatch) -> None:
    cursor = datetime(2025, 2, 20, 12, 0, 0, tzinfo=UTC).isoformat()
    state = _State(cursor_type="published_at", cursor_value=cursor, etag="etag-prev")
    ingestor = _build_ingestor_for_unit(
        article_repo=_FakeArticleRepo(
            IngestResult(run_id="run", items_seen=0, items_stored=0, items_skipped=0),
        ),
        state_repo=_FakeStateRepo({1: state}),
    )
    source = _FakeSource(id=1, name="Source One")

    async def _fetch_empty(*args: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], str | None]:
        return [], "W/123"

    monkeypatch.setattr(NewsIngestor, "_fetch_and_parse_source", _fetch_empty)
    result = await NewsIngestor._run_source(ingestor, source, "run-1")

    assert result.status == "completed_empty"
    assert len(ingestor._state_repo.success_updates) == 1
    assert ingestor._state_repo.success_updates[0][1]["cursor_value"] == cursor


@pytest.mark.asyncio
async def test_run_source_skips_when_in_backoff_window() -> None:
    state = _State(
        disabled_by_failure=True,
        next_retry_at=datetime.now(UTC) + timedelta(minutes=30),
        cursor_type="published_at",
        cursor_value="2025-02-20T12:00:00+00:00",
    )
    article_repo = _FakeArticleRepo(IngestResult())
    ingestor = _build_ingestor_for_unit(
        article_repo=article_repo,
        state_repo=_FakeStateRepo({1: state}),
    )
    source = _FakeSource(id=1, name="Blocked Source")

    result = await NewsIngestor._run_source(ingestor, source, "run-1")

    assert result.status == "skipped"
    assert result.error == "Source paused by backoff"
    assert not article_repo.calls


@pytest.mark.asyncio
async def test_run_ingest_isolated_failures_do_not_block_successful_sources() -> None:
    source_a = _FakeSource(1, "Primary")
    source_b = _FakeSource(2, "Secondary")
    article_repo = _FakeArticleRepo(IngestResult(run_id="run", items_seen=0, items_stored=0, items_skipped=0))
    run_repo = _FakeRunRepo()

    ingestor = _build_ingestor_for_unit(
        article_repo=article_repo,
        source_repo=_FakeSourceRepo([source_a, source_b]),
        run_repo=run_repo,
    )

    async def _run_source_stub(
        self: NewsIngestor,
        source: _FakeSource,
        run_id: str,
    ) -> SourceResult:
        if source.id == 1:
            return SourceResult(
                source_id=1,
                source_key=source.source_key,
                source_name=source.name,
                status="stored",
                items_seen=4,
                items_stored=4,
                items_skipped=0,
            )
        return SourceResult(
            source_id=2,
            source_key=source.source_key,
            source_name=source.name,
            status="failed",
            items_seen=1,
            items_stored=0,
            items_skipped=1,
            error="temporary error",
        )

    ingestor._run_source = _run_source_stub.__get__(ingestor, NewsIngestor)  # type: ignore[method-assign]
    news_ingest.initialize_schema = lambda: asyncio.sleep(0)  # type: ignore[method-assign]
    result = await ingestor.run_ingest(
        sources=[("Primary", "https://primary.example"), ("Secondary", "https://secondary.example")]
    )

    assert result.status == "partial"
    assert result.sources_processed == 2
    assert result.failed_sources == 1
    assert result.source_errors == 1
    assert result.items_stored == 4
    assert len(run_repo.created) == 1
    assert len(run_repo.finished) == 1


@pytest.mark.asyncio
async def test_source_health_returns_state_and_source_identity() -> None:
    source = _FakeSource(id=10, name="Reuters", enabled=True)
    state = _State(
        cursor_type="published_at",
        cursor_value="2025-02-20T11:00:00+00:00",
        consecutive_failures=2,
        last_success_at=datetime(2025, 2, 20, 11, 0, 0, tzinfo=UTC),
        last_error="temporary_error",
        next_retry_at=datetime(2025, 2, 20, 11, 5, 0, tzinfo=UTC),
        disabled_by_failure=True,
        last_latency_ms=123,
    )
    ingestor = _build_ingestor_for_unit(
        state_repo=_FakeStateRepo({10: state}),
        source_repo=_FakeSourceRepo([source]),
    )

    health = await ingestor.get_source_health()

    assert len(health) == 1
    first = health[0]
    assert first["source_id"] == 10
    assert first["source_key"] == source.source_key
    assert first["source_name"] == source.name
    assert first["source_category"] == source.source_category
    assert first["connector_type"] == source.connector_type
    assert first["provider_domain"] == source.provider_domain
    assert first["consecutive_failures"] == 2
    assert first["disabled_by_failure"] is True
    assert first["cursor_value"] == state.cursor_value
