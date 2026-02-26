#!/usr/bin/env python3
"""Unit tests for public source connectors (GDELT, SEC EDGAR, Newsdata.io)."""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from financial_news.services.connectors.gdelt import (
    GDELTConnector,
    _clean_text,
    _extract_entities,
    _extract_topics,
    _hash,
)
from financial_news.services.connectors.sec_edgar import SECEdgarConnector
from financial_news.services.connectors.newsdata import NewsdataConnector


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_gdelt_response(articles: list[dict] | None = None) -> dict:
    """Build a fake GDELT API response."""
    if articles is None:
        articles = [
            {
                "url": "https://example.com/finance-1",
                "title": "Stock Markets Rally on Earnings Hopes",
                "seendate": "20260225T120000Z",
                "domain": "example.com",
                "sourcecountry": "United States",
            },
            {
                "url": "https://example.com/finance-2",
                "title": "Federal Reserve Holds Rates Steady",
                "seendate": "20260225T143000Z",
                "domain": "reuters.com",
                "sourcecountry": "United States",
            },
        ]
    return {"articles": articles}


def _make_newsdata_response(results: list[dict] | None = None) -> dict:
    """Build a fake Newsdata.io API response."""
    if results is None:
        results = [
            {
                "title": "Global Economy Shows Signs of Recovery",
                "link": "https://news.example.com/economy-recovery",
                "description": "The global economy is showing early signs of recovery...",
                "pubDate": "2026-02-25T10:00:00Z",
                "source_id": "example_news",
                "image_url": None,
                "creator": ["John Doe"],
            },
        ]
    return {"status": "success", "results": results}


# ── GDELT Connector ─────────────────────────────────────────────────────────

class TestGDELTHelpers:
    def test_clean_text_removes_html(self):
        assert _clean_text("<p>Hello <b>World</b></p>") == "Hello World"

    def test_clean_text_collapses_whitespace(self):
        assert _clean_text("  hello   world  ") == "hello world"

    def test_clean_text_handles_entities(self):
        assert _clean_text("AT&amp;T &amp; Verizon") == "AT&T & Verizon"

    def test_hash_deterministic(self):
        assert _hash("test") == _hash("test")
        # _hash lowercases before hashing, so case variants match
        assert _hash("test") == _hash("TEST")
        assert _hash("test") != _hash("different")

    def test_extract_entities_finds_capitalized_words(self):
        entities = _extract_entities("Apple Inc reported strong results. Microsoft also gains.")
        assert any("Apple" in e for e in entities)
        assert any("Microsoft" in e for e in entities)

    def test_extract_entities_skips_stop_words(self):
        entities = _extract_entities("The market moves after This announcement.")
        assert "The" not in entities
        assert "This" not in entities

    def test_extract_entities_limits_to_six(self):
        text = "Alpha Beta Gamma Delta Epsilon Zeta Eta Theta Iota"
        entities = _extract_entities(text)
        assert len(entities) <= 6

    def test_extract_topics_finds_finance(self):
        topics = _extract_topics("The stock market saw record gains today")
        assert "Finance" in topics or "Markets" in topics

    def test_extract_topics_finds_ai(self):
        topics = _extract_topics("Artificial intelligence transforms financial services")
        assert "AI" in topics

    def test_extract_topics_defaults_to_markets(self):
        topics = _extract_topics("Nothing specific mentioned here at all")
        assert topics == ["Markets"]


class TestGDELTConnector:
    def test_default_queries(self):
        connector = GDELTConnector()
        assert len(connector.queries) == 3
        assert connector.max_articles == 25

    def test_custom_config(self):
        connector = GDELTConnector(
            queries=["custom query"],
            max_articles=10,
            timeout_seconds=5,
        )
        assert connector.queries == ["custom query"]
        assert connector.max_articles == 10

    @pytest.mark.asyncio
    async def test_fetch_articles_returns_dicts(self):
        connector = GDELTConnector(max_articles=5)
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=_make_gdelt_response())
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_class.return_value = mock_session

            articles = await connector.fetch_articles(source_id=1)

        assert isinstance(articles, list)
        assert len(articles) == 2
        for article in articles:
            assert "id" in article
            assert "title" in article
            assert "url" in article
            assert "source" in article
            assert "published_at" in article
            assert "sentiment" in article
            assert "topics" in article
            assert article["source_id"] == 1

    @pytest.mark.asyncio
    async def test_fetch_articles_deduplicates_urls(self):
        connector = GDELTConnector(max_articles=10)
        # Return same articles for different queries
        duplicate_articles = [
            {
                "url": "https://example.com/same-article",
                "title": "Same Article Twice",
                "seendate": "20260225T120000Z",
                "domain": "example.com",
            },
        ]
        response_data = {"articles": duplicate_articles}

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=response_data)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_class.return_value = mock_session

            articles = await connector.fetch_articles()

        # Should only have 1 copy despite 3 queries returning the same URL
        assert len(articles) == 1


# ── SEC EDGAR Connector ──────────────────────────────────────────────────────

class TestSECEdgarConnector:
    def test_default_config(self):
        connector = SECEdgarConnector()
        assert len(connector.queries) == 3
        assert connector.max_articles == 25
        assert len(connector.user_agent) > 0  # comes from env or default

    def test_custom_config(self):
        connector = SECEdgarConnector(
            queries=["8-K filings"],
            max_articles=5,
        )
        assert connector.queries == ["8-K filings"]
        assert connector.max_articles == 5

    @pytest.mark.asyncio
    async def test_fetch_articles_fallback_to_rss(self):
        """When EDGAR search returns non-200, it should fall back to RSS."""
        connector = SECEdgarConnector(max_articles=5)

        # Mock: EDGAR search returns 500, RSS returns a valid feed
        mock_search_resp = AsyncMock()
        mock_search_resp.status = 500
        mock_search_resp.__aenter__ = AsyncMock(return_value=mock_search_resp)
        mock_search_resp.__aexit__ = AsyncMock(return_value=False)

        mock_rss_resp = AsyncMock()
        mock_rss_resp.status = 200
        mock_rss_resp.text = AsyncMock(return_value="""<?xml version="1.0"?>
<rss version="2.0"><channel>
<item>
  <title>SEC Press Release: New Enforcement Action</title>
  <link>https://www.sec.gov/news/press-release/2026-42</link>
  <description>The SEC announced an enforcement action.</description>
  <pubDate>2026-02-25T10:00:00Z</pubDate>
</item>
</channel></rss>""")
        mock_rss_resp.__aenter__ = AsyncMock(return_value=mock_rss_resp)
        mock_rss_resp.__aexit__ = AsyncMock(return_value=False)

        call_count = 0
        def side_effect_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "efts.sec.gov" in url:
                return mock_search_resp
            return mock_rss_resp

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.get = MagicMock(side_effect=side_effect_get)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_class.return_value = mock_session

            articles = await connector.fetch_articles(source_id=2)

        assert isinstance(articles, list)
        # Should have gotten articles from RSS fallback
        for article in articles:
            assert "title" in article
            assert "url" in article
            assert article["source_id"] == 2


# ── Newsdata.io Connector ────────────────────────────────────────────────────

class TestNewsdataConnector:
    def test_is_available_without_key(self):
        connector = NewsdataConnector(api_key="")
        assert connector.is_available is False

    def test_is_available_with_key(self):
        connector = NewsdataConnector(api_key="test_key_123")
        assert connector.is_available is True

    @pytest.mark.asyncio
    async def test_fetch_articles_skips_without_key(self):
        connector = NewsdataConnector(api_key="")
        articles = await connector.fetch_articles()
        assert articles == []

    @pytest.mark.asyncio
    async def test_fetch_articles_with_valid_key(self):
        connector = NewsdataConnector(api_key="test_key", max_articles=5)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=_make_newsdata_response())
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_class.return_value = mock_session

            articles = await connector.fetch_articles(source_id=3)

        assert len(articles) == 1
        article = articles[0]
        assert article["title"] == "Global Economy Shows Signs of Recovery"
        assert article["source_id"] == 3
        assert "sentiment" in article
        assert "topics" in article

    @pytest.mark.asyncio
    async def test_fetch_articles_handles_rate_limit(self):
        connector = NewsdataConnector(api_key="test_key")

        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_class.return_value = mock_session

            articles = await connector.fetch_articles()

        assert articles == []

    @pytest.mark.asyncio
    async def test_fetch_articles_handles_invalid_key(self):
        connector = NewsdataConnector(api_key="invalid_key")

        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_class.return_value = mock_session

            articles = await connector.fetch_articles()

        assert articles == []
