"""GDELT Project connector — free, no API key, global news + events.

GDELT v2 DOC API: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
Endpoint: https://api.gdeltproject.org/api/v2/doc/doc
Rate limit: ~1 req/sec (no hard key), so we self-throttle to be polite.
"""

from __future__ import annotations

import hashlib
import html
import logging
import re
from datetime import datetime, timezone
from typing import Any

import aiohttp

from financial_news.core.sentiment import analyze_article_sentiment

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


def _clean_text(value: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", html.unescape(value or ""))).strip()


def _hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def _extract_entities(text: str) -> list[str]:
    """Simple capitalized-word entity extraction."""
    matches = re.findall(
        r"\b[A-Z][A-Za-z0-9&.'-]+(?:\s+[A-Z][A-Za-z0-9&.'-]+){0,2}\b", text
    )
    stop = {"The", "This", "There", "Your", "About", "After", "Since", "That", "But"}
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
        "Capital Markets": ["capital markets", "ipo", "bond market", "equity market"],
        "AI": ["artificial intelligence", "machine learning", "generative ai"],
        "Earnings": ["earnings", "revenue", "profit", "guidance"],
        "Policy": ["fed", "federal reserve", "interest rate", "regulation"],
        "Markets": ["market", "equity", "stock", "exchange", "dow", "nasdaq"],
        "Economy": ["economy", "gdp", "recession", "unemployment"],
    }
    topics = [t for t, kws in mapping.items() if any(k in low for k in kws)]
    return topics[:3] or ["Markets"]


class GDELTConnector:
    """Fetch financial news articles from GDELT v2 DOC API."""

    DEFAULT_QUERIES = [
        "finance stock market",
        "wall street economy",
        "earnings report",
    ]

    def __init__(
        self,
        *,
        queries: list[str] | None = None,
        max_articles: int = 25,
        timeout_seconds: int = 15,
    ) -> None:
        self.queries = queries or self.DEFAULT_QUERIES
        self.max_articles = max_articles
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def fetch_articles(
        self,
        source_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return normalized article dicts ready for upsert_deduplicated."""
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
                    logger.warning("GDELT query=%s error=%s", query, exc)

        logger.info("GDELT: fetched %d articles", len(all_articles))
        return all_articles

    async def _fetch_query(
        self,
        session: aiohttp.ClientSession,
        query: str,
        source_id: int | None,
    ) -> list[dict[str, Any]]:
        params = {
            "query": query,
            "mode": "ArtList",
            "maxrecords": str(min(self.max_articles, 75)),
            "format": "json",
            "sort": "DateDesc",
            "sourcelang": "eng",
        }
        async with session.get(GDELT_DOC_API, params=params) as resp:
            if resp.status != 200:
                logger.warning("GDELT HTTP %d for query=%s", resp.status, query)
                return []
            data = await resp.json(content_type=None)

        raw_articles = data.get("articles") or []
        results: list[dict[str, Any]] = []

        for item in raw_articles:
            title = _clean_text(item.get("title") or "")
            url = (item.get("url") or "").strip()
            if not title or not url:
                continue

            content = _clean_text(
                item.get("seendate") or item.get("title") or ""
            )
            # GDELT doesn't provide article body, use title as content
            full_text = title
            source_name = item.get("domain") or item.get("sourcecountry") or "GDELT"

            # Parse date — GDELT uses format like "20250225T123456Z"
            raw_date = item.get("seendate") or ""
            try:
                published_at = datetime.strptime(
                    raw_date, "%Y%m%dT%H%M%SZ"
                ).replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                published_at = datetime.now(timezone.utc)

            sentiment = analyze_article_sentiment(f"{title} {full_text}")

            record = {
                "id": _hash(f"{url}|{title}"),
                "source": f"GDELT – {source_name}",
                "source_name": f"GDELT – {source_name}",
                "source_id": source_id,
                "source_item_id": _hash(url),
                "published_at": published_at,
                "title": title,
                "url": url,
                "content": full_text,
                "summarized_headline": f"Summary: {title[:90]}",
                "summary_bullets": [title[:120]] if title else [],
                "sentiment": sentiment.get("sentiment"),
                "sentiment_score": sentiment.get("sentiment_score"),
                "market_impact_score": min(
                    1.0, abs((sentiment.get("sentiment_score") or 0.5) - 0.5) * 2
                ),
                "key_entities": _extract_entities(title),
                "topics": _extract_topics(title),
            }
            results.append(record)

        return results
