"""Reddit financial subreddit connector — free, no API key needed.

Scrapes public RSS feeds from popular finance subreddits:
- r/wallstreetbets  — retail investor sentiment, meme stocks
- r/investing       — long-term investment discussion
- r/stocks          — general stock discussion
- r/stockmarket     — market analysis
- r/economics       — macro economics
- r/personalfinance — personal finance (lower priority)

Reddit exposes every subreddit as an RSS feed at:
    https://www.reddit.com/r/{subreddit}/hot.rss

No API key, no OAuth, no rate-limit headers — just standard RSS.
"""

from __future__ import annotations

import hashlib
import html
import logging
import os
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp
import feedparser

from financial_news.core.sentiment import analyze_article_sentiment
from financial_news.services.connectors.base import BaseConnector

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# Subreddits ordered by financial relevance
DEFAULT_SUBREDDITS = [
    "wallstreetbets",
    "investing",
    "stocks",
    "stockmarket",
    "economics",
]
REDDIT_ALLOWED_DOMAIN = "reddit.com"
DEFAULT_REDDIT_RATE_BUDGET_PER_HOUR = 120
DEFAULT_REDDIT_PRECISION_THRESHOLD = 0.35
_REDDIT_BUDGET_STATE = {
    "window_started_at": datetime.now(UTC),
    "requests_used": 0,
}  # type: dict[str, datetime | int]
_SPAM_MARKERS = (
    "daily discussion",
    "what are your moves",
    "join our discord",
    "rate my portfolio",
    "meme",
    "shitpost",
)
_LOW_SIGNAL_MARKERS = ("yolo", "to the moon", "diamond hands", "bagholder")


def _clean_text(value: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", html.unescape(value or ""))).strip()


def _hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def _extract_tickers(text: str) -> list[str]:
    """Extract potential stock tickers like $AAPL or standalone 1-5 char uppercase."""
    # Match explicit $TICKER mentions
    dollar_tickers = re.findall(r"\$([A-Z]{1,5})\b", text)
    # Match standalone uppercase words that look like tickers (2-5 chars, in context)
    standalone = re.findall(r"\b([A-Z]{2,5})\b", text)
    # Filter common non-ticker words
    stop = {
        "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN",
        "HER", "WAS", "ONE", "OUR", "OUT", "DAY", "GET", "HAS", "HIM",
        "HOW", "ITS", "LET", "MAY", "NEW", "NOW", "OLD", "SEE", "WAY",
        "WHO", "DID", "GOT", "HIS", "SAY", "SHE", "TOO", "USE", "CEO",
        "IPO", "ETF", "GDP", "IMO", "TBH", "WSB", "DD", "YOLO", "FYI",
        "EOD", "ATH", "ITM", "OTM", "EPS", "PE", "LMAO", "EDIT", "TLDR",
        "USA", "NYSE", "SEC", "RSS", "API", "USD", "EUR", "GBP",
    }
    seen: set[str] = set()
    tickers: list[str] = []
    for t in dollar_tickers + standalone:
        if t in stop or t in seen:
            continue
        seen.add(t)
        tickers.append(t)
        if len(tickers) >= 6:
            break
    return tickers


def _extract_topics(text: str, subreddit: str) -> list[str]:
    """Extract topics based on text content and subreddit."""
    low = text.lower()
    topics: list[str] = []

    mapping = {
        "Finance": ["finance", "financial", "stock", "market"],
        "Earnings": ["earnings", "revenue", "profit", "guidance", "eps"],
        "Options": ["options", "calls", "puts", "strike", "expiry"],
        "Markets": ["market", "dow", "nasdaq", "s&p", "spy"],
        "Economy": ["economy", "gdp", "recession", "unemployment", "inflation"],
        "Crypto": ["crypto", "bitcoin", "ethereum", "btc", "eth"],
        "Real Estate": ["real estate", "housing", "mortgage", "reit"],
    }
    topics = [t for t, kws in mapping.items() if any(k in low for k in kws)]

    # Add subreddit-based tag
    sub_map = {
        "wallstreetbets": "Retail Sentiment",
        "investing": "Investment Strategy",
        "stocks": "Stocks",
        "stockmarket": "Market Analysis",
        "economics": "Macroeconomics",
    }
    if subreddit in sub_map and sub_map[subreddit] not in topics:
        topics.append(sub_map[subreddit])

    return topics[:3] or ["Markets"]


def _parse_subreddits_from_env() -> list[str]:
    raw = os.getenv("REDDIT_SUBREDDITS", "")
    if not raw.strip():
        return DEFAULT_SUBREDDITS
    parsed = [chunk.strip().lower() for chunk in raw.split(",") if chunk.strip()]
    return parsed or DEFAULT_SUBREDDITS


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_allowed_reddit_url(url: str) -> bool:
    normalized = url.strip().lower()
    return (
        normalized.startswith("https://www.reddit.com/")
        or normalized.startswith("https://reddit.com/")
    )


def _precision_score(
    title: str,
    content: str,
    subreddit: str,
    tickers: list[str],
) -> float:
    low_title = title.lower()
    low_content = content.lower()
    score = 0.0

    if tickers:
        score += 0.35
    if len(content) >= 120:
        score += 0.20
    if any(
        keyword in low_content
        for keyword in ("earnings", "guidance", "cpi", "fed", "rates", "revenue")
    ):
        score += 0.20
    if any(marker in low_content for marker in _LOW_SIGNAL_MARKERS):
        score -= 0.15
    if any(symbol in low_title for symbol in ("%", "$", "q1", "q2", "q3", "q4")):
        score += 0.10
    if subreddit in {"investing", "stocks", "stockmarket", "economics"}:
        score += 0.10

    return max(0.0, min(1.0, score))


def _is_spammy_post(title: str, content: str, precision_score: float) -> bool:
    low = f"{title} {content}".lower()
    if any(marker in low for marker in _SPAM_MARKERS):
        return True
    return len(content.strip()) < 40 and precision_score < 0.5


class RedditFinanceConnector(BaseConnector):
    """Fetch financial discussions from Reddit subreddit RSS feeds."""

    name = "Reddit Finance"
    requires_api_key = False

    def __init__(
        self,
        *,
        subreddits: list[str] | None = None,
        max_articles: int = 25,
        timeout_seconds: int = 15,
        sort: str = "hot",
        precision_threshold: float | None = None,
        rate_budget_per_hour: int | None = None,
    ) -> None:
        self.subreddits = subreddits or _parse_subreddits_from_env()
        self.max_articles = _coerce_int(
            os.getenv("REDDIT_MAX_ARTICLES", max_articles),
            max_articles,
        )
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.sort = os.getenv("REDDIT_SORT", sort).strip().lower() or sort  # hot/new/top
        configured_threshold = (
            precision_threshold
            if precision_threshold is not None
            else float(
                os.getenv(
                    "REDDIT_PRECISION_THRESHOLD",
                    str(DEFAULT_REDDIT_PRECISION_THRESHOLD),
                )
            )
        )
        self.precision_threshold = max(0.0, min(1.0, configured_threshold))
        self.rate_budget_per_hour = max(
            1,
            _coerce_int(
                os.getenv("REDDIT_RATE_BUDGET_PER_HOUR", rate_budget_per_hour),
                rate_budget_per_hour or DEFAULT_REDDIT_RATE_BUDGET_PER_HOUR,
            ),
        )

    def _consume_rate_budget(self) -> bool:
        now = datetime.now(UTC)
        window_started_at_raw = _REDDIT_BUDGET_STATE["window_started_at"]
        window_started_at = (
            window_started_at_raw
            if isinstance(window_started_at_raw, datetime)
            else now
        )
        if now - window_started_at >= timedelta(hours=1):
            _REDDIT_BUDGET_STATE["window_started_at"] = now
            _REDDIT_BUDGET_STATE["requests_used"] = 0

        requests_used_raw = _REDDIT_BUDGET_STATE["requests_used"]
        requests_used = (
            requests_used_raw if isinstance(requests_used_raw, int) else 0
        )
        if requests_used >= self.rate_budget_per_hour:
            return False

        _REDDIT_BUDGET_STATE["requests_used"] = requests_used + 1
        return True

    async def fetch_articles(
        self,
        source_id: int | None = None,
    ) -> list[ParsedArticle]:
        """Fetch posts from financial subreddits via RSS."""
        all_articles: list[ParsedArticle] = []
        seen_urls: set[str] = set()

        headers = {
            "User-Agent": "financenews-bot/1.0 (github.com/Fergonz1993/financenews)",
        }

        async with aiohttp.ClientSession(
            timeout=self.timeout, headers=headers
        ) as session:
            for subreddit in self.subreddits:
                if len(all_articles) >= self.max_articles:
                    break
                if not self._consume_rate_budget():
                    logger.warning(
                        "Reddit rate budget exhausted budget_per_hour=%d",
                        self.rate_budget_per_hour,
                    )
                    break
                try:
                    articles = await self._fetch_subreddit(
                        session, subreddit, source_id
                    )
                    for article in articles:
                        url = article.url
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)
                        all_articles.append(article)
                        if len(all_articles) >= self.max_articles:
                            break
                except Exception as exc:
                    logger.warning(
                        "Reddit r/%s error=%s", subreddit, exc
                    )

        logger.info("Reddit: fetched %d articles", len(all_articles))
        return all_articles

    async def _fetch_subreddit(
        self,
        session: aiohttp.ClientSession,
        subreddit: str,
        source_id: int | None,
    ) -> list[ParsedArticle]:
        """Fetch and parse a single subreddit RSS feed."""
        url = f"https://www.reddit.com/r/{subreddit}/{self.sort}.rss"

        async with session.get(url) as resp:
            if resp.status != 200:
                logger.warning(
                    "Reddit RSS HTTP %d for r/%s", resp.status, subreddit
                )
                return []
            text = await resp.text()

        feed = feedparser.parse(text)
        results: list[ParsedArticle] = []

        for entry in feed.entries:
            title = _clean_text(entry.get("title", ""))
            link = entry.get("link", "")
            if not title or not link:
                continue
            if not _is_allowed_reddit_url(link):
                continue

            # Extract content from the entry
            content = _clean_text(
                entry.get("summary", "")
                or entry.get("content", [{}])[0].get("value", "")
                if entry.get("content")
                else title
            )
            # Parse date
            published_parsed = entry.get("published_parsed")
            if published_parsed:
                try:
                    from time import mktime
                    published_at = datetime.fromtimestamp(
                        mktime(published_parsed), tz=UTC
                    )
                except (TypeError, ValueError, OverflowError):
                    published_at = datetime.now(UTC)
            else:
                published_at = datetime.now(UTC)

            sentiment = analyze_article_sentiment(f"{title} {content}")
            tickers = _extract_tickers(f"{title} {content}")
            precision = _precision_score(title, content, subreddit, tickers)
            if precision < self.precision_threshold:
                continue
            if _is_spammy_post(title, content, precision):
                continue

            record = ParsedArticle(
                id=_hash(f"reddit|{link}"),
                source_name=f"Reddit - r/{subreddit}",
                source_id=source_id,
                source_item_id=_hash(link),
                published_at=published_at,
                title=f"[r/{subreddit}] {title}",
                url=link,
                content=content[:5000],
                summarized_headline=f"Summary: {title[:90]}",
                summary_bullets=[title[:120]] if title else [],
                sentiment=sentiment.get("sentiment"),
                sentiment_score=sentiment.get("sentiment_score"),
                market_impact_score=min(
                    1.0,
                    abs((sentiment.get("sentiment_score") or 0.5) - 0.5) * 2,
                ),
                key_entities=tickers or _extract_tickers(title),
                topics=_extract_topics(f"{title} {content}", subreddit),
                relevance_precision=round(precision, 3),
            )
            results.append(record)

        return results
