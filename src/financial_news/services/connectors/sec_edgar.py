"""SEC EDGAR public data connector — free, no API key required.

Fetches press releases and recent filings from SEC's public APIs:
- EDGAR Full-Text Search API: https://efts.sec.gov/LATEST/search-index
- RSS Feeds: SEC press releases and filing updates

Rate limit: SEC asks for 10 req/sec max with proper User-Agent.
See: https://www.sec.gov/os/webmaster-faq#developers
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

# SEC EDGAR endpoints
EDGAR_FULL_TEXT_SEARCH = "https://efts.sec.gov/LATEST/search-index"
EDGAR_SUBMISSIONS_RECENT = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_PRESS_RSS = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=8-K&dateb=&owner=include&count=40&search_text=&action=getcompany&output=atom"


def _clean_text(value: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", html.unescape(value or ""))).strip()


def _hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def _extract_entities(text: str) -> list[str]:
    matches = re.findall(
        r"\b[A-Z][A-Za-z0-9&.'-]+(?:\s+[A-Z][A-Za-z0-9&.'-]+){0,2}\b", text
    )
    stop = {"The", "This", "There", "Your", "About", "After", "Since", "That", "SEC"}
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
        "SEC Filing": ["sec", "filing", "8-k", "10-k", "10-q", "form"],
        "Finance": ["finance", "financial", "stock", "market"],
        "Earnings": ["earnings", "revenue", "profit"],
        "Policy": ["regulation", "enforcement", "compliance", "rule"],
        "Capital Markets": ["ipo", "offering", "capital"],
    }
    topics = [t for t, kws in mapping.items() if any(k in low for k in kws)]
    return topics[:3] or ["SEC Filing"]


class SECEdgarConnector(BaseConnector):
    """Fetch recent SEC press releases and filings via EDGAR full-text search."""

    name = "SEC EDGAR"
    requires_api_key = False

    DEFAULT_QUERIES = [
        "earnings",
        "financial results",
        "SEC enforcement",
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
        self.user_agent = os.getenv(
            "SEC_API_USER_AGENT",
            "finnews-ingest/1.0 (contact@example.com)",
        )
        self.request_delay = float(
            os.getenv("SEC_API_REQUEST_DELAY_SECONDS", "0.5")
        )

    async def fetch_articles(
        self,
        source_id: int | None = None,
    ) -> list[ParsedArticle]:
        """Return normalized article models from SEC EDGAR full-text search."""
        all_articles: list[ParsedArticle] = []
        seen_urls: set[str] = set()

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

        async with aiohttp.ClientSession(
            timeout=self.timeout, headers=headers
        ) as session:
            for query in self.queries:
                if len(all_articles) >= self.max_articles:
                    break
                try:
                    articles = await self._search_edgar(
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
                    logger.warning("SEC EDGAR query=%s error=%s", query, exc)

                # Be polite to SEC servers
                import asyncio
                await asyncio.sleep(self.request_delay)

        logger.info("SEC EDGAR: fetched %d articles", len(all_articles))
        return all_articles

    async def _search_edgar(
        self,
        session: aiohttp.ClientSession,
        query: str,
        source_id: int | None,
    ) -> list[ParsedArticle]:
        """Use EDGAR full-text search API."""
        params = {
            "q": query,
            "dateRange": "custom",
            "startdt": "",
            "enddt": "",
            "forms": "8-K,10-K,10-Q,6-K",
        }

        search_url = "https://efts.sec.gov/LATEST/search-index"
        try:
            async with session.get(search_url, params=params) as resp:
                if resp.status != 200:
                    # Fallback to RSS-based approach
                    return await self._fetch_press_rss(session, source_id)
                data = await resp.json(content_type=None)
        except Exception:
            return await self._fetch_press_rss(session, source_id)

        hits = data.get("hits", {}).get("hits", [])
        results: list[ParsedArticle] = []

        for hit in hits[: self.max_articles]:
            src = hit.get("_source", {})
            title = _clean_text(src.get("display_names", [""])[0] if src.get("display_names") else src.get("file_description", "SEC Filing"))
            file_date = src.get("file_date") or src.get("period_of_report") or ""
            form_type = src.get("form_type", "")
            file_num = src.get("file_num", "")

            if not title:
                title = f"SEC {form_type} Filing"

            # Build URL to SEC filing
            accession = src.get("accession_no") or hit.get("_id", "")
            url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&filenum={file_num}&type={form_type}&dateb=&owner=include&count=10" if file_num else f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type={form_type}"

            try:
                published_at = datetime.fromisoformat(file_date).replace(
                    tzinfo=timezone.utc
                )
            except (ValueError, TypeError):
                published_at = datetime.now(timezone.utc)

            content = f"{form_type} filing: {title}"
            sentiment = analyze_article_sentiment(content)

            record = ParsedArticle(
                id=_hash(f"sec|{accession}|{title}"),
                source_name="SEC EDGAR",
                source_id=source_id,
                source_item_id=_hash(accession or url),
                published_at=published_at,
                title=f"[{form_type}] {title}" if form_type else title,
                url=url,
                content=content,
                summarized_headline=f"Summary: {title[:90]}",
                summary_bullets=[content[:120]],
                sentiment=sentiment.get("sentiment"),
                sentiment_score=sentiment.get("sentiment_score"),
                market_impact_score=min(
                    1.0, abs((sentiment.get("sentiment_score") or 0.5) - 0.5) * 2
                ),
                key_entities=_extract_entities(title),
                topics=_extract_topics(content),
            )
            results.append(record)

        return results

    async def _fetch_press_rss(
        self,
        session: aiohttp.ClientSession,
        source_id: int | None,
    ) -> list[ParsedArticle]:
        """Fallback: parse SEC press releases RSS."""
        import feedparser

        press_url = os.getenv(
            "SEC_PRESS_RELEASE_FEEDS",
            "https://www.sec.gov/newsroom/press-releases/rss?output=atom",
        )
        try:
            async with session.get(press_url) as resp:
                if resp.status != 200:
                    return []
                text = await resp.text()
        except Exception as exc:
            logger.warning("SEC press RSS error: %s", exc)
            return []

        feed = feedparser.parse(text)
        results: list[ParsedArticle] = []

        for entry in feed.entries[: self.max_articles]:
            title = _clean_text(entry.get("title", ""))
            link = entry.get("link", "")
            if not title:
                continue

            content = _clean_text(
                entry.get("summary") or entry.get("description") or title
            )
            try:
                published_at = datetime.fromisoformat(
                    entry.get("published", "").replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                published_at = datetime.now(timezone.utc)

            sentiment = analyze_article_sentiment(f"{title} {content}")

            record = ParsedArticle(
                id=_hash(f"sec-press|{link}"),
                source_name="SEC Press Releases",
                source_id=source_id,
                source_item_id=_hash(link),
                published_at=published_at,
                title=title,
                url=link,
                content=content,
                summarized_headline=f"Summary: {title[:90]}",
                summary_bullets=[content[:120]] if content else [],
                sentiment=sentiment.get("sentiment"),
                sentiment_score=sentiment.get("sentiment_score"),
                market_impact_score=min(
                    1.0,
                    abs((sentiment.get("sentiment_score") or 0.5) - 0.5) * 2,
                ),
                key_entities=_extract_entities(title),
                topics=_extract_topics(f"{title} {content}"),
            )
            results.append(record)

        return results
