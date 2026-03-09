#!/usr/bin/env python3
"""Additional API helper tests — raise coverage for api/main.py utility layer."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import financial_news.api.main as api_main


# ---------------------------------------------------------------------------
# _coerce_float / _coerce_list (api module versions)
# ---------------------------------------------------------------------------
class TestApiCoerceFloat:
    def test_valid(self) -> None:
        assert api_main._coerce_float("3.14") == pytest.approx(3.14)

    def test_none(self) -> None:
        assert api_main._coerce_float(None) is None

    def test_invalid(self) -> None:
        assert api_main._coerce_float("nope") is None


class TestApiCoerceList:
    def test_from_list(self) -> None:
        assert api_main._coerce_list(["a", "b"]) == ["a", "b"]

    def test_from_scalar(self) -> None:
        assert api_main._coerce_list("solo") == ["solo"]

    def test_empty(self) -> None:
        assert api_main._coerce_list(None) == []
        assert api_main._coerce_list("") == []


# ---------------------------------------------------------------------------
# _normalize_search_text
# ---------------------------------------------------------------------------
class TestNormalizeSearchText:
    def test_lowercases(self) -> None:
        assert api_main._normalize_search_text("HELLO") == "hello"

    def test_strips_special_chars(self) -> None:
        result = api_main._normalize_search_text("Hello, World! #2026")
        assert result == "hello world 2026"

    def test_list_input(self) -> None:
        result = api_main._normalize_search_text(["Fed", "Reserve"])
        assert result == "fed reserve"

    def test_empty(self) -> None:
        assert api_main._normalize_search_text("") == ""
        assert api_main._normalize_search_text(None) == ""


# ---------------------------------------------------------------------------
# _normalize_article_payload
# ---------------------------------------------------------------------------
class TestNormalizeArticlePayload:
    def test_fills_defaults(self) -> None:
        raw = {"id": "a1", "title": "Test"}
        result = api_main._normalize_article_payload(raw)
        assert result["id"] == "a1"
        assert result["title"] == "Test"
        assert result["source"] == "Unknown"
        assert result["summary_bullets"] == []
        assert result["key_entities"] == []
        assert result["topics"] == []
        assert result["sentiment"] is None
        assert result["sentiment_score"] is None
        assert result["market_impact_score"] is None

    def test_preserves_values(self) -> None:
        raw = {
            "id": "a2",
            "title": "Market Rally",
            "url": "https://example.com/rally",
            "source": "Reuters",
            "published_at": "2026-01-15T00:00:00Z",
            "summarized_headline": "Markets up",
            "summary_bullets": ["Strong earnings", "Tech leads"],
            "sentiment": "positive",
            "sentiment_score": 0.85,
            "market_impact_score": 0.7,
            "key_entities": ["AAPL", "MSFT"],
            "topics": ["Markets", "Earnings"],
        }
        result = api_main._normalize_article_payload(raw)
        assert result["source"] == "Reuters"
        assert result["sentiment"] == "positive"
        assert result["sentiment_score"] == pytest.approx(0.85)
        assert result["key_entities"] == ["AAPL", "MSFT"]


# ---------------------------------------------------------------------------
# _slugify_filter_value
# ---------------------------------------------------------------------------
class TestSlugifyFilterValue:
    def test_basic(self) -> None:
        result = api_main._slugify_filter_value("Reuters News")
        assert isinstance(result, str)
        assert result == result.lower()

    def test_none(self) -> None:
        result = api_main._slugify_filter_value(None)
        assert result == ""


# ---------------------------------------------------------------------------
# _is_valid_entity_name
# ---------------------------------------------------------------------------
class TestIsValidEntityName:
    def test_valid(self) -> None:
        assert api_main._is_valid_entity_name("Federal Reserve") is True
        assert api_main._is_valid_entity_name("AAPL") is True

    def test_invalid(self) -> None:
        assert api_main._is_valid_entity_name(None) is False
        assert api_main._is_valid_entity_name("") is False


# ---------------------------------------------------------------------------
# _env_int
# ---------------------------------------------------------------------------
class TestEnvInt:
    def test_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_ENV_INT", "42")
        assert api_main._env_int("TEST_ENV_INT", 0) == 42

    def test_missing(self) -> None:
        assert api_main._env_int("NONEXISTENT_VAR_XYZ", 7) == 7

    def test_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_ENV_INT_BAD", "oops")
        assert api_main._env_int("TEST_ENV_INT_BAD", 3) == 3


# ---------------------------------------------------------------------------
# _build_analytics_payload
# ---------------------------------------------------------------------------
class TestBuildAnalyticsPayload:
    @pytest.mark.asyncio
    async def test_aggregates_sentiment_and_source_counts(self) -> None:
        articles = [
            {
                "sentiment": "positive",
                "source": "Reuters",
                "key_entities": ["AAPL", "Fed"],
                "topics": ["Markets"],
            },
            {
                "sentiment": "positive",
                "source": "Reuters",
                "key_entities": ["AAPL"],
                "topics": ["Markets", "Earnings"],
            },
            {
                "sentiment": "negative",
                "source": "CNBC",
                "key_entities": ["TSLA"],
                "topics": ["Earnings"],
            },
        ]
        # Mock the ingester's get_last_run
        fake_run = SimpleNamespace(finished_at=None)
        original = api_main.ingester.get_last_run
        api_main.ingester.get_last_run = AsyncMock(return_value=fake_run)
        try:
            result = await api_main._build_analytics_payload(articles)
        finally:
            api_main.ingester.get_last_run = original

        assert result["sentiment_distribution"]["positive"] == 2
        assert result["sentiment_distribution"]["negative"] == 1
        assert result["source_distribution"]["Reuters"] == 2
        assert result["source_distribution"]["CNBC"] == 1
        assert result["processing_stats"]["articles_processed"] == 3
        # top_entities should include AAPL with count 2
        entity_names = [e["name"] for e in result["top_entities"]]
        assert "AAPL" in entity_names

    @pytest.mark.asyncio
    async def test_empty_articles(self) -> None:
        fake_run = SimpleNamespace(finished_at=None)
        original = api_main.ingester.get_last_run
        api_main.ingester.get_last_run = AsyncMock(return_value=fake_run)
        try:
            result = await api_main._build_analytics_payload([])
        finally:
            api_main.ingester.get_last_run = original

        assert result["sentiment_distribution"] == {}
        assert result["source_distribution"] == {}
        assert result["top_entities"] == []
        assert result["top_topics"] == []
        assert result["processing_stats"]["articles_processed"] == 0


# ---------------------------------------------------------------------------
# _parse_csv_filters / _parse_csv_source_urls / _parse_csv_source_ids
# ---------------------------------------------------------------------------
class TestCsvParsers:
    def test_parse_csv_filters_none(self) -> None:
        assert api_main._parse_csv_filters(None) is None

    def test_parse_csv_filters_valid(self) -> None:
        result = api_main._parse_csv_filters("reuters,cnbc,bbc")
        assert len(result) == 3

    def test_parse_csv_source_urls_none(self) -> None:
        assert api_main._parse_csv_source_urls(None) is None

    def test_parse_csv_source_urls_valid(self) -> None:
        result = api_main._parse_csv_source_urls(
            "https://example.com/feed,https://other.com/rss"
        )
        assert len(result) == 2

    def test_parse_csv_source_ids_none(self) -> None:
        assert api_main._parse_csv_source_ids(None) is None

    def test_parse_csv_source_ids_from_string(self) -> None:
        result = api_main._parse_csv_source_ids("1,2,3")
        assert result == [1, 2, 3]

    def test_parse_csv_source_ids_from_list(self) -> None:
        result = api_main._parse_csv_source_ids([10, 20])
        assert result == [10, 20]


# ---------------------------------------------------------------------------
# _resolve_user_id / _default_user_settings / _default_user_alerts
# ---------------------------------------------------------------------------
class TestUserHelpers:
    def test_default_user_settings_shape(self) -> None:
        settings = api_main._default_user_settings()
        assert "darkMode" in settings
        assert "autoRefresh" in settings
        assert "refreshInterval" in settings
        assert "defaultFilters" in settings
        assert "emailAlerts" in settings

    def test_default_user_alerts_shape(self) -> None:
        alerts = api_main._default_user_alerts()
        assert "enabled" in alerts
        assert "rules" in alerts

    def test_normalize_user_settings_none(self) -> None:
        result = api_main._normalize_user_settings(None)
        assert result["darkMode"] is True  # default

    def test_normalize_user_alerts_none(self) -> None:
        result = api_main._normalize_user_alerts(None)
        assert result["enabled"] is False  # default


# ---------------------------------------------------------------------------
# _normalize_filter_list
# ---------------------------------------------------------------------------
class TestNormalizeFilterList:
    def test_from_list(self) -> None:
        result = api_main._normalize_filter_list(["reuters", "cnbc"])
        assert result == ["reuters", "cnbc"]

    def test_from_csv_string(self) -> None:
        result = api_main._normalize_filter_list("reuters,cnbc")
        assert len(result) == 2

    def test_none(self) -> None:
        assert api_main._normalize_filter_list(None) is None
