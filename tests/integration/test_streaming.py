"""Deterministic integration tests for continuous ingestion orchestration.

These tests avoid live network dependencies and validate mixed-connector
behavior, payload validation, and replay safety using mocked connectors.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from financial_news.services.continuous_runner import ContinuousIngestRunner


class _GoodConnector:
    async def fetch_articles(self, source_id: int | None = None):
        return [
            {
                "id": "good-1",
                "source": "Good Source",
                "source_id": source_id,
                "title": "Market rallies after CPI cools",
                "url": "https://example.com/good-1",
                "content": "US equities rose as inflation data softened.",
                "published_at": "2026-02-28T12:00:00+00:00",
                "summary_bullets": ["Equities rose", "Inflation cooled"],
                "topics": ["Markets"],
                "key_entities": ["Federal Reserve"],
            }
        ]


class _InvalidPayloadConnector:
    async def fetch_articles(self, source_id: int | None = None):
        # Missing URL should be rejected by validator.
        return [
            {
                "id": "invalid-1",
                "source": "Invalid Source",
                "source_id": source_id,
                "title": "Payload without URL",
                "content": "Invalid payload",
                "published_at": "2026-02-28T12:00:00+00:00",
            }
        ]


class _FailingConnector:
    async def fetch_articles(self, source_id: int | None = None):
        raise RuntimeError("upstream timeout")


class _FakeNewsIngestor:
    def __init__(self, session_factory=None) -> None:
        self.session_factory = session_factory

    async def run_ingest(self):
        return SimpleNamespace(items_seen=4, items_stored=1, sources_processed=2)


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch) -> ContinuousIngestRunner:
    runner = ContinuousIngestRunner(session_factory=AsyncMock())

    runner._CONNECTOR_FACTORIES = {
        "good": ("Good Connector", _GoodConnector),
        "invalid": ("Invalid Connector", _InvalidPayloadConnector),
        "failing": ("Failing Connector", _FailingConnector),
    }

    runner._configured_connector_enabled = {
        "good": True,
        "invalid": True,
        "failing": True,
    }
    runner._connector_events = {name: [] for name in runner._CONNECTOR_FACTORIES}
    runner._connector_status = {}
    runner._connector_runtime_overrides = {}

    sources = [
        SimpleNamespace(id=11, source_key="connector-good"),
        SimpleNamespace(id=12, source_key="connector-invalid"),
        SimpleNamespace(id=13, source_key="connector-failing"),
    ]
    runner._source_repo = SimpleNamespace(
        upsert_sources=AsyncMock(return_value=[]),
        list_sources=AsyncMock(return_value=sources),
    )

    runner._article_repo = SimpleNamespace(
        upsert_deduplicated=AsyncMock(return_value=SimpleNamespace(items_stored=2)),
    )

    monkeypatch.setattr(
        "financial_news.services.continuous_runner.initialize_schema",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "financial_news.services.news_ingest.NewsIngestor",
        _FakeNewsIngestor,
    )

    return runner


@pytest.mark.integration
@pytest.mark.asyncio
async def test_continuous_runner_handles_mixed_connector_outcomes(
    runner: ContinuousIngestRunner,
):
    result = await runner.trigger_immediate()

    assert result["status"] == "partial"
    assert result["articles_stored"] == 3

    connector_results = result["results"]
    assert connector_results["good"]["state"] in {"ready", "degraded"}
    assert connector_results["good"]["articles_validated"] == 1
    assert connector_results["invalid"]["articles_rejected"] == 1
    assert connector_results["failing"]["state"] == "error"
    assert connector_results["failing"]["error_code"] == "timeout"

    status = runner.get_status()
    assert "connectors" in status
    assert status["connectors"]["good"]["enabled"] is True
    assert status["connectors"]["failing"]["state"] == "error"
    assert status["connectors"]["good"]["slo_24h"]["events"] >= 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_continuous_runner_replay_is_idempotent(runner: ContinuousIngestRunner):
    runner._article_repo.upsert_deduplicated = AsyncMock(
        side_effect=[
            SimpleNamespace(items_stored=2),
            SimpleNamespace(items_stored=0),
        ]
    )

    first = await runner.trigger_immediate()
    second = await runner.trigger_immediate()

    assert first["results"]["good"]["articles_stored"] == 2
    assert second["results"]["good"]["articles_stored"] == 0


@pytest.mark.integration
def test_connector_runtime_toggle_controls(runner: ContinuousIngestRunner):
    disabled = runner.set_connector_enabled("good", False)
    assert disabled["effective_enabled"] is False

    cleared = runner.clear_connector_override("good")
    assert cleared["runtime_override"] is None
    assert cleared["effective_enabled"] is True
