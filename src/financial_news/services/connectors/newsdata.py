"""Newsdata.io connector — free tier: 200 requests/day.

Provides structured news articles via REST API with built-in topic/country
filtering. Completely optional; skips gracefully when no API key is set.

API docs: https://newsdata.io/documentation
"""

from __future__ import annotations

import hashlib
import html
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

import aiohttp

from financial_news.core.sentiment import analyze_article_sentiment
from financial_news.services.connectors.base import BaseConnector

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

NEWSDATA_API = "https://newsdata.io/api/1/news"


def _clean_text(value: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", html.unescape(value or ""))).strip()


def _hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def _extract_entities(text: str) -> list[str]:
    matches = re.findall(
        r"\b[A-Z][A-Za-z0-9&.'-]+(?:\s+[A-Z][A-Za-z0-9&.'-]+){0,2}\b", text
    )
    stop = {"The", "This", "There", "Your", "About", "After", "Since", "That"}
    seen: set[str] = set()
    items: list[str] = []
    for tok in matches:
        c = tok.strip()
        if c in stop or len(c) < 3:
            continue
        n = c.lower()
        if n in seen:
            continue
        seen.add(n)
        items.append(c)
        if len(items) >= 6:
            break
    return items


def _extract_topics(text: str) -> list[str]:
    low = text.lower()
    mapping = {
        "Finance": ["finance", "financial", "stock", "market", "inflation"],
        "Capital Markets": ["capital markets", "ipo", "bond", "equity market"],
        "AI": ["artificial intelligence", "machine learning", "generative ai"],
        "Earnings": ["earnings", "revenue", "profit", "guidance"],
        "Policy": ["fed", "federal reserve", "interest rate", "regulation"],
        "Markets": ["market", "equity", "stock", "exchange", "dow", "nasdaq"],
        "Economy": ["economy", "gdp", "recession", "unemployment"],
    }
    topics = [t for t, kws in mapping.items() if any(k in low for k in kws)]
    return topics[:3] or ["Markets"]


class NewsdataConnector(BaseConnector):
    """Fetch financial news from Newsdata.io (free tier, API key required)."""

    name = "Newsdata.io"
    requires_api_key = True

    DEFAULT_QUERIES = ["finance", "stock market", "economy"]

    def __init__(
        self,
        *,
        api_key: str | None = None,
        queries: list[str] | None = None,
        max_articles: int = 25,
        timeout_seconds: int = 15,
        country: str = "us",
        language: str = "en",
        category: str = "business",
    ) -> None:
        self.api_key = api_key or os.getenv("NEWSDATA_API_KEY", "")
        self.queries = queries or self.DEFAULT_QUERIES
        self.max_articles = max_articles
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.country = country
        self.language = language
        self.category = category

    @property
    def is_available(self) -> bool:
        """Check if the connector has a valid API key."""
        return bool(self.api_key and self.api_key.strip())

    async def fetch_articles(
        self,
        source_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return normalized article dicts. Skips gracefully if no API key."""
        if not self.is_available:
            logger.info(
                "Newsdata.io: skipping — no NEWSDATA_API_KEY configured"
            )
            return []

        all_articles: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            for query in self.queries:
                if len(all_articles) >= self.max_articles:
                    break
                try:
                    articles = await self._fetch_query(
                        session, query, source_id
                    )
                    for article in articles:
                        url = article.get("url", "")
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)
                        all_articles.append(article)
                        if len(all_articles) >= self.max_articles:
                            break
                except Exception as exc:
                    logger.warning("Newsdata.io query=%s error=%s", query, exc)

        logger.info("Newsdata.io: fetched %d articles", len(all_articles))
        return all_articles

    async def _fetch_query(
        self,
        session: aiohttp.ClientSession,
        query: str,
        source_id: int | None,
    ) -> list[dict[str, Any]]:
        params = {
            "apikey": self.api_key,
            "q": query,
            "country": self.country,
            "language": self.language,
            "category": self.category,
        }
        async with session.get(NEWSDATA_API, params=params) as resp:
            if resp.status == 401:
                logger.warning("Newsdata.io: invalid API key")
                return []
            if resp.status == 429:
                logger.warning("Newsdata.io: rate limit exceeded")
                return []
            if resp.status != 200:
                logger.warning(
                    "Newsdata.io HTTP %d for query=%s", resp.status, query
                )
                return []
            data = await resp.json(content_type=None)

        raw_articles = data.get("results") or []
        results: list[dict[str, Any]] = []

        for item in raw_articles:
            title = _clean_text(item.get("title") or "")
            url = (item.get("link") or "").strip()
            if not title or not url:
                continue

            content = _clean_text(
                item.get("content")
                or item.get("description")
                or title
            )
            source_name = item.get("source_id") or "Newsdata.io"

            # Parse date
            raw_date = item.get("pubDate") or ""
            try:
                published_at = datetime.fromisoformat(
                    raw_date.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                published_at = datetime.now(timezone.utc)

            image_url = item.get("image_url")
            creator = item.get("creator")
            author = creator[0] if isinstance(creator, list) and creator else None

            sentiment = analyze_article_sentiment(f"{title} {content}")

            record = {
                "id": _hash(f"newsdata|{url}"),
                "source": f"Newsdata – {source_name}",
                "source_name": f"Newsdata – {source_name}",
                "source_id": source_id,
                "source_item_id": _hash(url),
                "published_at": published_at,
                "title": title,
                "url": url,
                "content": content[:5000],
                "summarized_headline": f"Summary: {title[:90]}",
                "summary_bullets": [
                    s.strip()
                    for s in re.split(r"[.!?]", content)
                    if len(s.strip()) > 24
                ][:3],
                "sentiment": sentiment.get("sentiment"),
                "sentiment_score": sentiment.get("sentiment_score"),
                "market_impact_score": min(
                    1.0,
                    abs((sentiment.get("sentiment_score") or 0.5) - 0.5) * 2,
                ),
                "key_entities": _extract_entities(f"{title} {content}"),
                "topics": _extract_topics(f"{title} {content}"),
            }
            results.append(record)

        return results
