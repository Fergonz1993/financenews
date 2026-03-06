"""Deterministic integration tests for continuous ingestion orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from financial_news.services.continuous_runner import ContinuousIngestRunner


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_cycle_handles_validation_degradation(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop_initialize_schema() -> None:
        return None

    monkeypatch.setattr(
        "financial_news.services.continuous_runner.initialize_schema",
        _noop_initialize_schema,
    )

    class _FakeConnector:
        async def fetch_articles(self, source_id: int | None = None):
            return [
                {
                    "id": "valid-1",
                    "title": "Fed signals hold on rates",
                    "url": "https://example.com/fed-signals-hold",
                    "source": "GDELT",
                    "published_at": datetime(2026, 2, 25, tzinfo=UTC),
                    "content": "Market commentary",
                    "topics": ["Policy"],
                },
                {
                    "id": "invalid-1",
                    "title": "",
                    "url": "https://example.com/invalid",
                    "source": "GDELT",
                    "published_at": datetime(2026, 2, 25, tzinfo=UTC),
                    "content": "Invalid because title empty",
                },
            ]

    class _FakeIngestResult:
        items_seen = 0
        items_stored = 0
        sources_processed = 0

    class _FakeNewsIngestor:
        def __init__(self, session_factory=None) -> None:
            self._session_factory = session_factory

        async def run_ingest(self):
            return _FakeIngestResult()

    monkeypatch.setattr(
        "financial_news.services.news_ingest.NewsIngestor",
        _FakeNewsIngestor,
    )

    runner = ContinuousIngestRunner.__new__(ContinuousIngestRunner)
    runner._session_factory = SimpleNamespace()
    runner._article_repo = SimpleNamespace(
        upsert_deduplicated=AsyncMock(
            return_value=SimpleNamespace(items_stored=1)
        )
    )
    runner._source_repo = SimpleNamespace(
        upsert_sources=AsyncMock(return_value=[]),
        list_sources=AsyncMock(
            return_value=[SimpleNamespace(id=12, source_key="connector-gdelt")]
        ),
    )
    runner._running = False
    runner._task = None
    runner._cycle_count = 0
    runner._last_cycle_at = None
    runner._last_cycle_articles = 0
    runner._total_articles_ingested = 0
    runner._errors = []
    runner._connector_status = {}
    runner._connector_events = []
    runner.enabled = True
    runner.interval_seconds = 300
    runner._CONNECTOR_FACTORIES = {
        "gdelt": ("GDELT Project", object),
        "sec_edgar": ("SEC EDGAR", object),
        "newsdata": ("Newsdata.io", object),
        "reddit": ("Reddit Finance", object),
    }
    runner._configured_connector_enabled = {
        "gdelt": True,
        "sec_edgar": False,
        "newsdata": False,
        "reddit": False,
    }
    runner._connector_runtime_overrides = {}
    runner._stock_correlator_enabled = False
    runner._stock_correlator = None
    runner._build_connector_instances = lambda: [("gdelt", _FakeConnector())]

    result = await runner._run_cycle()

    assert result["cycle"] == 1
    assert result["articles_stored"] == 1
    assert result["results"]["gdelt"]["state"] == "degraded"
    assert result["results"]["gdelt"]["articles_fetched"] == 2
    assert runner._connector_status["gdelt"]["state"] == "degraded"
    assert runner._connector_status["gdelt"]["error_code"] == "validation_error"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_cycle_enrichment_fail_open(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop_initialize_schema() -> None:
        return None

    monkeypatch.setattr(
        "financial_news.services.continuous_runner.initialize_schema",
        _noop_initialize_schema,
    )

    class _FakeConnector:
        async def fetch_articles(self, source_id: int | None = None):
            return [
                {
                    "id": "valid-1",
                    "title": "NVIDIA reports strong demand",
                    "url": "https://example.com/nvda-demand",
                    "source": "GDELT",
                    "published_at": datetime(2026, 2, 25, tzinfo=UTC),
                    "content": "AI demand remains strong",
                }
            ]

    class _FailingCorrelator:
        def enrich_articles(self, articles):
            raise RuntimeError("market data provider unavailable")

    class _FakeIngestResult:
        items_seen = 0
        items_stored = 0
        sources_processed = 0

    class _FakeNewsIngestor:
        def __init__(self, session_factory=None) -> None:
            self._session_factory = session_factory

        async def run_ingest(self):
            return _FakeIngestResult()

    monkeypatch.setattr(
        "financial_news.services.news_ingest.NewsIngestor",
        _FakeNewsIngestor,
    )

    runner = ContinuousIngestRunner.__new__(ContinuousIngestRunner)
    runner._session_factory = SimpleNamespace()
    runner._article_repo = SimpleNamespace(
        upsert_deduplicated=AsyncMock(return_value=SimpleNamespace(items_stored=1))
    )
    runner._source_repo = SimpleNamespace(
        upsert_sources=AsyncMock(return_value=[]),
        list_sources=AsyncMock(
            return_value=[SimpleNamespace(id=12, source_key="connector-gdelt")]
        ),
    )
    runner._running = False
    runner._task = None
    runner._cycle_count = 0
    runner._last_cycle_at = None
    runner._last_cycle_articles = 0
    runner._total_articles_ingested = 0
    runner._errors = []
    runner._connector_status = {}
    runner._connector_events = {}
    runner.enabled = True
    runner.interval_seconds = 300
    runner._CONNECTOR_FACTORIES = {
        "gdelt": ("GDELT Project", _FakeConnector),
    }
    runner._configured_connector_enabled = {
        "gdelt": True,
    }
    runner._connector_runtime_overrides = {}
    runner._stock_correlator_enabled = True
    runner._stock_correlator = _FailingCorrelator()
    runner._near_dedup_enabled = False
    runner._near_dedup_similarity_threshold = 0.92

    result = await runner._run_cycle()

    assert result["status"] == "completed"
    assert result["articles_stored"] == 1
    assert result["results"]["gdelt"]["state"] == "ready"
    assert any(
        item.get("error_code") == "enrichment_error" for item in runner._errors
    )
