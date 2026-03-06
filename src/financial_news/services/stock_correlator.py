"""Stock price correlator — enriches articles with market data via yfinance.

When ``yfinance`` is installed, this service can:
1. Extract stock tickers from article text
2. Fetch price data around the article's publish time
3. Calculate a news→price impact correlation score

This turns your news aggregator into a **news intelligence** platform.

Usage::

    from financial_news.services.stock_correlator import StockCorrelator

    correlator = StockCorrelator()
    enriched = await correlator.enrich_article(article_dict)
    # article_dict now has 'price_data' and 'price_impact' fields

Install::

    pip install yfinance
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Well-known ticker → company mapping for better extraction
KNOWN_TICKERS: dict[str, str] = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "GOOGL": "Alphabet",
    "GOOG": "Alphabet",
    "AMZN": "Amazon",
    "META": "Meta",
    "TSLA": "Tesla",
    "NVDA": "NVIDIA",
    "JPM": "JPMorgan",
    "V": "Visa",
    "JNJ": "Johnson & Johnson",
    "WMT": "Walmart",
    "PG": "Procter & Gamble",
    "UNH": "UnitedHealth",
    "HD": "Home Depot",
    "DIS": "Disney",
    "BAC": "Bank of America",
    "NFLX": "Netflix",
    "AMD": "AMD",
    "INTC": "Intel",
    "CRM": "Salesforce",
    "PYPL": "PayPal",
    "COIN": "Coinbase",
    "GME": "GameStop",
    "AMC": "AMC",
    "PLTR": "Palantir",
    "SOFI": "SoFi",
    "RIVN": "Rivian",
    "NIO": "NIO",
}

# Company name → ticker reverse map
_COMPANY_TO_TICKER = {v.lower(): k for k, v in KNOWN_TICKERS.items()}

# Words that look like tickers but aren't
_STOP_WORDS = {
    "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN",
    "CEO", "IPO", "ETF", "GDP", "RSS", "API", "USD", "EUR", "GBP",
    "SEC", "FED", "IMF", "WHO", "GDP", "CPI", "PMI", "NFP", "USA",
    "NYSE", "DOW", "EDIT", "TLDR", "YOLO", "IMO", "FYI", "EOD",
}


def _is_yfinance_available() -> bool:
    """Check if yfinance is installed."""
    try:
        import yfinance  # noqa: F401
        return True
    except ImportError:
        return False


def extract_tickers(text: str) -> list[str]:
    """Extract stock tickers from text.

    Looks for:
    1. Explicit $TICKER mentions (highest confidence)
    2. Known company names mapped to tickers
    3. Standalone uppercase 2-5 char words that might be tickers
    """
    tickers: list[str] = []
    seen: set[str] = set()

    # 1. Explicit $TICKER
    for match in re.findall(r"\$([A-Z]{1,5})\b", text):
        if match not in seen:
            seen.add(match)
            tickers.append(match)

    # 2. Known company names
    text_lower = text.lower()
    for company, ticker in _COMPANY_TO_TICKER.items():
        if company in text_lower and ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)

    # 3. Known tickers appearing as plain uppercase
    for ticker in KNOWN_TICKERS:
        if ticker not in seen and re.search(rf"\b{ticker}\b", text):
            seen.add(ticker)
            tickers.append(ticker)

    return tickers[:6]


class StockCorrelator:
    """Enrich articles with stock price data."""

    def __init__(self, lookback_days: int = 5, lookahead_days: int = 2) -> None:
        self.lookback_days = lookback_days
        self.lookahead_days = lookahead_days

    def enrich_article(self, article: dict[str, Any]) -> dict[str, Any]:
        """Add price data and impact scores to an article dict.

        Modifies the article dict in-place and returns it.
        """
        if not _is_yfinance_available():
            logger.debug("yfinance not installed, skipping enrichment")
            return article

        # Extract tickers from title + content
        text = f"{article.get('title', '')} {article.get('content', '')}"
        tickers = extract_tickers(text)

        if not tickers:
            return article

        import yfinance as yf

        published_at = article.get("published_at")
        if isinstance(published_at, str):
            try:
                published_at = datetime.fromisoformat(published_at)
            except ValueError:
                published_at = datetime.now(timezone.utc)

        if published_at is None:
            published_at = datetime.now(timezone.utc)

        start = published_at - timedelta(days=self.lookback_days)
        end = published_at + timedelta(days=self.lookahead_days)

        price_data: list[dict[str, Any]] = []

        for ticker in tickers[:3]:  # Limit API calls
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(start=start, end=end)

                if hist.empty:
                    continue

                # Calculate price change around article date
                pre_price = hist["Close"].iloc[0] if len(hist) > 0 else None
                post_price = hist["Close"].iloc[-1] if len(hist) > 0 else None

                if pre_price and post_price:
                    pct_change = ((post_price - pre_price) / pre_price) * 100
                else:
                    pct_change = 0.0

                price_data.append({
                    "ticker": ticker,
                    "company": KNOWN_TICKERS.get(ticker, ticker),
                    "pre_price": round(float(pre_price), 2) if pre_price else None,
                    "post_price": round(float(post_price), 2) if post_price else None,
                    "pct_change": round(pct_change, 2),
                    "period": f"{self.lookback_days}d before → {self.lookahead_days}d after",
                })
            except Exception as exc:
                logger.debug("yfinance error for %s: %s", ticker, exc)

        if price_data:
            article["price_data"] = price_data
            article["mentioned_tickers"] = tickers

            # Calculate aggregate impact score
            avg_abs_change = sum(
                abs(p["pct_change"]) for p in price_data
            ) / len(price_data)
            # Normalise: 5%+ change = 1.0 impact
            article["price_impact"] = min(1.0, avg_abs_change / 5.0)

        return article

    def enrich_articles(
        self, articles: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Enrich a batch of articles with price data."""
        for article in articles:
            try:
                self.enrich_article(article)
            except Exception as exc:
                logger.debug("Enrichment failed for article: %s", exc)
        return articles
