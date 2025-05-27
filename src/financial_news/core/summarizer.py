#!/usr/bin/env python3
"""
Enhanced Financial News Summarizer Agent
A production-ready AI-powered tool for financial news analysis with advanced features.
"""

import asyncio

# Email and notifications
import functools
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import aiofiles

# Core libraries
import aiohttp
import cachetools
import click

# Utilities
import colorlog
import dotenv
import feedparser

# Financial data sources
# Data processing
import pandas as pd
import redis
import tiktoken
import yaml
from asyncio_throttle import Throttler
from fuzzywuzzy import fuzz

# OpenAI and caching
from openai import AsyncOpenAI
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Load environment variables
dotenv.load_dotenv()


# Configure enhanced logging with caching
@lru_cache(maxsize=1)
def setup_logging():
    """Setup enhanced logging with colors - cached for performance."""
    handler = colorlog.StreamHandler()
    handler.setFormatter(
        colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
        )
    )

    logger = logging.getLogger("enhanced_news_summarizer")
    if not logger.handlers:  # Avoid duplicate handlers
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, os.getenv("LOG_LEVEL", "INFO")))
    return logger


logger = setup_logging()


# Enhanced configuration class with slots for memory optimization
@dataclass
class Config:
    """Enhanced configuration management with dataclass for better performance."""

    __slots__ = ("_config_cache", "config", "config_path")

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        self._config_cache = None
        self.config = self._load_config()
        self._validate_config()

    @functools.cached_property
    def _loaded_config(self) -> dict:
        """Load configuration from YAML file - cached as property."""
        try:
            with open(self.config_path) as f:
                config = yaml.safe_load(f)
            logger.info(f"✅ Configuration loaded from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"❌ Error loading config: {e}")
            return self._get_default_config()

    def _load_config(self) -> dict:
        """Load configuration using cached property."""
        return self._loaded_config

    @staticmethod
    def _get_default_config() -> dict:
        """Get default configuration if file is missing."""
        return {
            "queries": ["AAPL", "MSFT", "GOOGL"],
            "ai": {"model": "gpt-4o-mini", "temperature": 0.3, "max_tokens": 500},
            "processing": {"max_articles": 25, "concurrent_requests": 5},
        }

    def _validate_config(self):
        """Validate configuration."""
        required_keys = ["queries", "ai", "processing"]
        for key in required_keys:
            if key not in self.config:
                logger.warning(f"⚠️  Missing config section: {key}")

    def get(self, key: str, default=None):
        """Get configuration value with dot notation - using instance cache."""
        if not hasattr(self, "_get_cache"):
            self._get_cache = {}

        if key in self._get_cache:
            return self._get_cache[key]

        keys = key.split(".")
        value = self.config
        try:
            for k in keys:
                value = value[k]
            self._get_cache[key] = value
            return value
        except (KeyError, TypeError):
            self._get_cache[key] = default
            return default


# Enhanced Article class with slots for memory optimization
@dataclass
class Article:
    """Enhanced article representation with slots for memory efficiency."""

    __slots__ = (
        "content",
        "id",
        "key_entities",
        "market_impact_score",
        "processed_at",
        "processing_time",
        "published_at",
        "relevance_score",
        "sentiment",
        "sentiment_score",
        "source",
        "summarized_headline",
        "summary_bullets",
        "title",
        "topics",
        "url",
        "why_it_matters",
        "word_count",
    )

    def __init__(
        self, title: str, url: str, source: str, published_at: str, content: str
    ):
        self.id = hashlib.md5(
            f"{title}{url}".encode(), usedforsecurity=False
        ).hexdigest()
        self.title = title
        self.url = url
        self.source = source
        self.published_at = published_at
        self.content = content

        # AI-generated fields
        self.summarized_headline: str | None = None
        self.summary_bullets: list[str] = []
        self.why_it_matters: str | None = None
        self.sentiment: str | None = None
        self.sentiment_score: float | None = None
        self.market_impact_score: float | None = None
        self.relevance_score: float | None = None
        self.key_entities: list[str] = []
        self.topics: list[str] = []

        # Metadata
        self.processed_at: datetime | None = None
        self.processing_time: float | None = None
        self.word_count: int = len(content.split()) if content else 0

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Article):
            return False
        return self.id == other.id

    def to_dict(self) -> dict:
        """Convert article to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at,
            "content": self.content,
            "summarized_headline": self.summarized_headline,
            "summary_bullets": self.summary_bullets,
            "why_it_matters": self.why_it_matters,
            "sentiment": self.sentiment,
            "sentiment_score": self.sentiment_score,
            "market_impact_score": self.market_impact_score,
            "relevance_score": self.relevance_score,
            "key_entities": self.key_entities,
            "topics": self.topics,
            "word_count": self.word_count,
            "processed_at": (
                self.processed_at.isoformat() if self.processed_at else None
            ),
        }


# Enhanced caching system with connection pooling
class CacheManager:
    """Enhanced caching with Redis and memory fallback."""

    __slots__ = ("memory_cache", "redis_client", "stats")

    def __init__(self):
        self.redis_client = self._init_redis()
        # Use TTL cache for memory efficiency
        self.memory_cache = cachetools.TTLCache(maxsize=1000, ttl=3600)
        self.stats = {"hits": 0, "misses": 0}

    def _init_redis(self):
        """Initialize Redis client with connection pooling."""
        try:
            redis_client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=0,
                decode_responses=True,
                connection_pool=redis.ConnectionPool(max_connections=10),
            )
            redis_client.ping()
            logger.info("✅ Redis cache connected")
            return redis_client
        except Exception as e:
            logger.warning(f"⚠️  Redis unavailable, using memory cache: {e}")
            return None

    async def get(self, key: str) -> str | None:
        """Get value from cache with fallback."""
        # Try memory cache first (fastest)
        if key in self.memory_cache:
            self.stats["hits"] += 1
            return self.memory_cache[key]

        # Try Redis cache
        if self.redis_client:
            try:
                value = self.redis_client.get(key)
                if value:
                    self.memory_cache[key] = value  # Store in memory for next time
                    self.stats["hits"] += 1
                    return value
            except Exception as e:
                logger.error(f"Redis get error: {e}")

        self.stats["misses"] += 1
        return None

    async def set(self, key: str, value: str, ttl: int | None = None):
        """Set value in cache with TTL."""
        # Always store in memory cache
        self.memory_cache[key] = value

        # Store in Redis if available
        if self.redis_client:
            try:
                if ttl:
                    self.redis_client.setex(key, ttl, value)
                else:
                    self.redis_client.set(key, value)
            except Exception as e:
                logger.error(f"Redis set error: {e}")

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total if total > 0 else 0
        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate": hit_rate,
            "memory_size": len(self.memory_cache),
        }


# Enhanced News Fetcher with connection pooling
class EnhancedNewsFetcher:
    """Enhanced news fetcher with connection pooling and rate limiting."""

    __slots__ = (
        "cache",
        "config",
        "finnhub_client",
        "rss_feeds",
        "session",
        "stats",
        "throttler",
    )

    def __init__(
        self,
        session: aiohttp.ClientSession,
        config: Config,
        cache: CacheManager,
    ):
        self.session = session
        self.config = config
        self.cache = cache
        # Use better rate limiting
        self.throttler = Throttler(
            rate_limit=config.get("processing.concurrent_requests", 5)
        )
        self.finnhub_client = self._init_finnhub()
        self.rss_feeds = self._get_rss_feeds()
        self.stats = {"fetched": 0, "cached": 0, "errors": 0}

    def _init_finnhub(self):
        """Initialize Finnhub client if API key is available."""
        api_key = os.getenv("FINNHUB_API_KEY")
        if api_key:
            logger.info("✅ Finnhub API key found")
            return api_key
        logger.warning("⚠️  Finnhub API key not found")
        return None

    @functools.cached_property
    def _rss_feeds(self) -> dict[str, str]:
        """Get RSS feed URLs - cached as property."""
        return {
            "Reuters Business": "https://feeds.reuters.com/reuters/businessNews",
            "BBC Business": "http://feeds.bbci.co.uk/news/business/rss.xml",
            "CNN Business": "http://rss.cnn.com/rss/money_latest.rss",
            "MarketWatch": "http://feeds.marketwatch.com/marketwatch/topstories/",
            "Yahoo Finance": "https://feeds.finance.yahoo.com/rss/2.0/headline",
        }

    def _get_rss_feeds(self) -> dict[str, str]:
        """Get RSS feed URLs using cached property."""
        return self._rss_feeds

    async def fetch_from_newsapi(self, query: str) -> list[Article]:
        """Fetch news articles from NewsAPI with caching."""
        cache_key = f"newsapi:{query}:{datetime.now().hour}"
        cached_result = await self.cache.get(cache_key)

        if cached_result:
            self.stats["cached"] += 1
            try:
                data = json.loads(cached_result)
                return [Article(**article_data) for article_data in data]
            except Exception as e:
                logger.error(f"Cache deserialization error: {e}")

        # Skip if NewsAPI key is not configured
        api_key = os.getenv("NEWS_API_KEY")
        if not api_key or api_key == "your_newsapi_key_here":
            logger.warning("NewsAPI key not configured, skipping NewsAPI source")
            return []

        async with self.throttler:
            try:
                url = "https://newsapi.org/v2/everything"
                params = {
                    "q": query,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": min(
                        100, self.config.get("processing.max_articles", 25)
                    ),
                    "apiKey": api_key,
                }

                timeout = aiohttp.ClientTimeout(total=30)
                async with self.session.get(
                    url, params=params, timeout=timeout
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"NewsAPI error: {error_text}")
                        self.stats["errors"] += 1
                        return []

                    data = await response.json()
                    articles = []

                    for item in data.get("articles", []):
                        if not self._should_include_article(item):
                            continue

                        article = Article(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            source=item.get("source", {}).get("name", "Unknown"),
                            published_at=item.get("publishedAt", ""),
                            content=item.get("content", item.get("description", "")),
                        )
                        articles.append(article)

                    # Cache results for 1 hour
                    cache_data = [article.to_dict() for article in articles]
                    await self.cache.set(cache_key, json.dumps(cache_data), ttl=3600)

                    self.stats["fetched"] += len(articles)
                    return articles

            except asyncio.TimeoutError:
                logger.error("NewsAPI request timeout")
                self.stats["errors"] += 1
                return []
            except Exception as e:
                logger.error(f"Error fetching from NewsAPI: {e}")
                self.stats["errors"] += 1
                return []

    def _should_include_article(self, article_data: dict) -> bool:
        """Determine if article should be included based on quality filters."""
        title = article_data.get("title", "")
        content = article_data.get("content", "") or article_data.get("description", "")

        # Filter out low-quality articles
        if not title or len(title) < 10:
            return False

        if not content or len(content) < 50:
            return False

        # Filter out common spam patterns
        spam_indicators = [
            "[Removed]",
            "Click here",
            "Subscribe",
            "Download our app",
            "This content is not available",
        ]

        for indicator in spam_indicators:
            if indicator.lower() in content.lower():
                return False

        # Check for financial relevance
        financial_keywords = [
            "stock",
            "market",
            "trading",
            "finance",
            "investment",
            "economy",
            "earnings",
            "revenue",
            "profit",
            "loss",
            "share",
            "dividend",
            "analyst",
            "forecast",
        ]

        text_to_check = f"{title} {content}".lower()
        return any(keyword in text_to_check for keyword in financial_keywords)

    async def fetch_from_rss_feeds(self, query: str) -> list[Article]:
        """Fetch articles from multiple RSS feeds concurrently."""
        tasks = []
        for source_name, feed_url in self.rss_feeds.items():
            task = self._fetch_rss_feed(feed_url, source_name, query)
            tasks.append(task)

        # Use asyncio.gather for concurrent execution
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"RSS feed error: {result}")
                self.stats["errors"] += 1
            elif isinstance(result, list):
                all_articles.extend(result)

        return all_articles

    async def _fetch_rss_feed(
        self, feed_url: str, source_name: str, query: str
    ) -> list[Article]:
        """Fetch articles from a specific RSS feed with caching."""
        cache_key = f"rss:{source_name}:{datetime.now().hour}"
        cached_result = await self.cache.get(cache_key)

        if cached_result:
            self.stats["cached"] += 1
            try:
                data = json.loads(cached_result)
                articles = [Article(**article_data) for article_data in data]
                # Filter for relevance to query
                return [
                    article
                    for article in articles
                    if self._is_relevant_to_query(
                        article.title + " " + article.content, query
                    )
                ]
            except Exception as e:
                logger.error(f"RSS cache deserialization error: {e}")

        try:
            # Use feedparser with better error handling
            news_feed = feedparser.parse(feed_url)

            if news_feed.bozo:
                logger.warning(f"RSS feed parsing issues for {source_name}")

            articles = []
            for entry in news_feed.entries[:50]:  # Limit entries for performance
                title = entry.get("title", "")
                url = entry.get("link", "")
                published_at = entry.get("published", "")

                # Get content from various possible fields
                content = (
                    entry.get("summary", "")
                    or entry.get("description", "")
                    or getattr(entry, "content", [{}])[0].get("value", "")
                    if hasattr(entry, "content") and entry.content
                    else ""
                )

                if self._is_relevant_to_query(f"{title} {content}", query):
                    article = Article(
                        title=title,
                        url=url,
                        source=source_name,
                        published_at=published_at,
                        content=content,
                    )
                    articles.append(article)

            # Cache results
            cache_data = [article.to_dict() for article in articles]
            await self.cache.set(cache_key, json.dumps(cache_data), ttl=3600)

            self.stats["fetched"] += len(articles)
            return articles

        except Exception as e:
            logger.error(f"Error fetching RSS feed {source_name}: {e}")
            self.stats["errors"] += 1
            return []

    def _is_relevant_to_query(self, text: str, query: str) -> bool:
        """Check if text is relevant to query using fuzzy matching - with instance cache."""
        if not hasattr(self, "_relevance_cache"):
            self._relevance_cache = cachetools.LRUCache(maxsize=1000)

        cache_key = f"{text[:100]}:{query}"  # Use first 100 chars to avoid huge keys

        if cache_key in self._relevance_cache:
            return self._relevance_cache[cache_key]

        # Convert to lowercase for comparison
        text_lower = text.lower()
        query_lower = query.lower()

        # Direct substring match
        if query_lower in text_lower:
            result = True
        else:
            # Fuzzy matching for partial matches
            result = fuzz.partial_ratio(query_lower, text_lower) > 70

        self._relevance_cache[cache_key] = result
        return result

    async def fetch_news(self, queries: list[str]) -> list[Article]:
        """Fetch news from all sources for given queries."""
        all_articles = set()  # Use set for automatic deduplication

        for query in queries:
            logger.info(f"🔍 Fetching news for: {query}")

            # Create tasks for concurrent fetching
            tasks = [
                self.fetch_from_newsapi(query),
                self.fetch_from_rss_feeds(query),
            ]

            # Execute tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Fetch error for {query}: {result}")
                elif isinstance(result, list):
                    all_articles.update(result)

        # Convert back to list and limit results
        articles_list = list(all_articles)
        max_articles = self.config.get("processing.max_articles", 25)

        # Sort by published date (most recent first)
        articles_list.sort(
            key=lambda x: x.published_at if x.published_at else "",
            reverse=True,
        )

        return articles_list[:max_articles]

    def get_stats(self) -> dict:
        """Get fetching statistics."""
        return self.stats.copy()


# Enhanced News Summarizer with async optimization
class EnhancedNewsSummarizer:
    """Enhanced summarizer with async optimization and intelligent caching."""

    __slots__ = ("cache", "client", "config", "stats", "tokenizer")

    def __init__(self, config: Config, cache: CacheManager):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.config = config
        self.cache = cache
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.stats = {"processed": 0, "cached": 0, "tokens_used": 0, "errors": 0}

    async def summarize_article(self, article: Article) -> Article:
        """Summarize a single article with caching and error handling."""
        start_time = time.time()

        # Check cache first
        cache_key = f"summary:{article.id}"
        cached_summary = await self.cache.get(cache_key)

        if cached_summary:
            try:
                summary_data = json.loads(cached_summary)
                self._populate_article_from_summary(article, summary_data)
                article.processed_at = datetime.now()
                article.processing_time = time.time() - start_time
                self.stats["cached"] += 1
                return article
            except Exception as e:
                logger.error(f"Cache deserialization error: {e}")

        # Prepare content with token limit
        content = self._prepare_content(article)
        if not content.strip():
            self._populate_fallback_summary(article)
            return article

        try:
            # Create enhanced prompt
            prompt = self._create_enhanced_prompt(content)

            # Count tokens
            token_count = len(self.tokenizer.encode(prompt))
            self.stats["tokens_used"] += token_count

            # Call OpenAI API with optimized parameters
            response = await self.client.chat.completions.create(
                model=self.config.get("ai.model", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.get("ai.temperature", 0.3),
                max_tokens=self.config.get("ai.max_tokens", 500),
                timeout=30.0,  # 30 second timeout
            )

            summary_text = response.choices[0].message.content.strip()

            # Parse the structured response
            try:
                summary_data = json.loads(summary_text)
                self._populate_article_from_summary(article, summary_data)

                # Cache the result for 24 hours
                await self.cache.set(cache_key, summary_text, ttl=86400)

            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse AI response as JSON for article {article.id}"
                )
                self._populate_fallback_summary(article)

        except Exception as e:
            logger.error(f"Error summarizing article {article.id}: {e}")
            self._populate_fallback_summary(article)
            self.stats["errors"] += 1

        article.processed_at = datetime.now()
        article.processing_time = time.time() - start_time
        self.stats["processed"] += 1
        return article

    def _prepare_content(self, article: Article) -> str:
        """Prepare article content with token optimization."""
        content = f"Title: {article.title}\n\nContent: {article.content}"

        # Limit content to prevent token overflow
        max_tokens = 3000  # Leave room for prompt and response
        tokens = self.tokenizer.encode(content)

        if len(tokens) > max_tokens:
            # Truncate and decode back to text
            truncated_tokens = tokens[:max_tokens]
            content = self.tokenizer.decode(truncated_tokens)
            logger.debug(f"Truncated content for article {article.id}")

        return content

    def _create_enhanced_prompt(self, content: str) -> str:
        """Create an optimized prompt for AI summarization."""
        return f"""
Analyze this financial news article and provide a structured summary in JSON format:

{content}

Return ONLY a valid JSON object with these exact keys:
{{
    "summarized_headline": "A concise, engaging headline (max 80 chars)",
    "summary_bullets": ["3-5 key points as brief bullet points"],
    "why_it_matters": "Why this news is significant for investors/markets (1-2 sentences)",
    "sentiment": "positive/negative/neutral",
    "sentiment_score": 0.0,
    "market_impact_score": 0.0,
    "key_entities": ["company names, people, important terms"],
    "topics": ["main topic categories"]
}}

Keep responses concise and focused on financial impact. Sentiment and market impact scores should be between -1.0 and 1.0.
"""

    def _populate_article_from_summary(self, article: Article, summary_data: dict):
        """Populate article fields from AI summary data."""
        article.summarized_headline = summary_data.get("summarized_headline")
        article.summary_bullets = summary_data.get("summary_bullets", [])
        article.why_it_matters = summary_data.get("why_it_matters")
        article.sentiment = summary_data.get("sentiment")
        article.sentiment_score = summary_data.get("sentiment_score")
        article.market_impact_score = summary_data.get("market_impact_score")
        article.key_entities = summary_data.get("key_entities", [])
        article.topics = summary_data.get("topics", [])

    def _populate_fallback_summary(self, article: Article):
        """Populate with fallback summary when AI fails."""
        article.summarized_headline = (
            article.title[:80] + "..." if len(article.title) > 80 else article.title
        )
        article.summary_bullets = ["Original article content available"]
        article.why_it_matters = "Please refer to the full article for details."
        article.sentiment = "neutral"
        article.sentiment_score = 0.0
        article.market_impact_score = 0.0
        article.key_entities = []
        article.topics = ["general"]

    async def summarize_articles(self, articles: list[Article]) -> list[Article]:
        """Summarize multiple articles concurrently with optimized batching."""
        if not articles:
            return []

        logger.info(f"📝 Summarizing {len(articles)} articles...")

        # Create semaphore to limit concurrent API calls
        semaphore = asyncio.Semaphore(
            self.config.get("processing.concurrent_requests", 5)
        )

        async def summarize_with_semaphore(article):
            async with semaphore:
                return await self.summarize_article(article)

        # Use list comprehension for better performance
        summarized = await asyncio.gather(
            *[summarize_with_semaphore(article) for article in articles],
            return_exceptions=True,
        )

        # Filter out exceptions and return successful results
        valid_articles = []
        for result in summarized:
            if isinstance(result, Exception):
                logger.error(f"Summarization error: {result}")
                self.stats["errors"] += 1
            elif isinstance(result, Article):
                valid_articles.append(result)

        # Sort by market impact score and sentiment
        valid_articles.sort(
            key=lambda x: (x.market_impact_score or 0, x.sentiment_score or 0),
            reverse=True,
        )

        return valid_articles

    def get_stats(self) -> dict:
        """Get summarization statistics."""
        return self.stats.copy()


# Enhanced Analytics
class NewsAnalytics:
    """Advanced analytics for news data."""

    def __init__(self):
        self.df = None

    def analyze_articles(self, articles: list[Article]) -> dict:
        """Perform comprehensive analysis on articles."""
        if not articles:
            return {}

        # Convert to DataFrame for analysis
        data = [article.to_dict() for article in articles]
        self.df = pd.DataFrame(data)

        analytics = {
            "total_articles": len(articles),
            "sentiment_distribution": self._analyze_sentiment(),
            "source_distribution": self._analyze_sources(),
            "top_entities": self._analyze_entities(articles),
            "trending_topics": self._analyze_topics(articles),
            "market_impact_summary": self._analyze_market_impact(),
            "processing_stats": self._analyze_processing_stats(),
        }

        return analytics

    def _analyze_sentiment(self) -> dict:
        """Analyze sentiment distribution."""
        if "sentiment" not in self.df.columns:
            return {}

        sentiment_counts = self.df["sentiment"].value_counts()
        avg_sentiment_score = self.df["sentiment_score"].mean()

        return {
            "distribution": sentiment_counts.to_dict(),
            "average_score": (
                float(avg_sentiment_score) if not pd.isna(avg_sentiment_score) else 0.0
            ),
            "positive_ratio": len(self.df[self.df["sentiment"] == "positive"])
            / len(self.df),
            "negative_ratio": len(self.df[self.df["sentiment"] == "negative"])
            / len(self.df),
        }

    def _analyze_sources(self) -> dict:
        """Analyze source distribution."""
        source_counts = self.df["source"].value_counts()
        return {
            "distribution": source_counts.to_dict(),
            "total_sources": len(source_counts),
            "top_source": source_counts.index[0] if len(source_counts) > 0 else None,
        }

    def _analyze_entities(self, articles: list[Article]) -> list[dict]:
        """Analyze key entities mentioned."""
        entity_counts = {}

        for article in articles:
            for entity in article.key_entities:
                entity_counts[entity] = entity_counts.get(entity, 0) + 1

        # Sort by frequency
        sorted_entities = sorted(
            entity_counts.items(), key=lambda x: x[1], reverse=True
        )

        return [
            {"entity": entity, "count": count} for entity, count in sorted_entities[:10]
        ]

    def _analyze_topics(self, articles: list[Article]) -> list[dict]:
        """Analyze trending topics."""
        topic_counts = {}

        for article in articles:
            for topic in article.topics:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1

        # Sort by frequency
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)

        return [{"topic": topic, "count": count} for topic, count in sorted_topics[:10]]

    def _analyze_market_impact(self) -> dict:
        """Analyze market impact scores."""
        if "market_impact_score" not in self.df.columns:
            return {}

        return {
            "average_impact": float(self.df["market_impact_score"].mean()),
            "high_impact_count": len(self.df[self.df["market_impact_score"] > 0.7]),
            "low_impact_count": len(self.df[self.df["market_impact_score"] < 0.3]),
        }

    def _analyze_processing_stats(self) -> dict:
        """Analyze processing performance."""
        if "processing_time" not in self.df.columns:
            return {}

        processing_times = self.df["processing_time"].dropna()

        return {
            "average_processing_time": (
                float(processing_times.mean()) if len(processing_times) > 0 else 0
            ),
            "total_processing_time": (
                float(processing_times.sum()) if len(processing_times) > 0 else 0
            ),
            "articles_processed": len(processing_times),
        }


# Enhanced Output Manager
class EnhancedOutputManager:
    """Enhanced output manager with multiple formats and destinations."""

    def __init__(self, config: Config, console: Console):
        self.config = config
        self.console = console
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.briefings_dir = Path("./briefings")
        self.briefings_dir.mkdir(exist_ok=True)

    async def output_all(self, articles: list[Article], analytics: dict):
        """Output to all configured destinations."""
        results = {}

        if self.config.get("output.console", True):
            self.output_to_console(articles, analytics)
            results["console"] = True

        if self.config.get("output.markdown", True):
            md_path = await self.output_to_markdown(articles, analytics)
            results["markdown"] = md_path

        if self.config.get("output.json", False):
            json_path = await self.output_to_json(articles, analytics)
            results["json"] = json_path

        if self.config.get("output.email", False):
            email_sent = await self.output_to_email(articles)
            results["email"] = email_sent

        return results

    def output_to_console(self, articles: list[Article], analytics: dict):
        """Enhanced console output with analytics."""
        # Header
        self.console.print(
            f"\n[bold green]📈 Financial News Briefing • {self.today}[/bold green]"
        )

        # Analytics summary
        if analytics:
            self._print_analytics_summary(analytics)

        # Articles
        self.console.print(
            f"\n[bold cyan]📰 Top Stories ({len(articles)} articles)[/bold cyan]\n"
        )

        for i, article in enumerate(articles, 1):
            self._print_article_console(article, i)

    def _print_analytics_summary(self, analytics: dict):
        """Print analytics summary to console."""
        table = Table(
            title="📊 Analytics Summary", show_header=True, header_style="bold magenta"
        )
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="yellow")

        # Add key metrics
        table.add_row("Total Articles", str(analytics.get("total_articles", 0)))

        sentiment = analytics.get("sentiment_distribution", {})
        if sentiment:
            sentiment_summary = f"😊 {sentiment.get('positive', 0)} | 😐 {sentiment.get('neutral', 0)} | 😟 {sentiment.get('negative', 0)}"
            table.add_row("Sentiment", sentiment_summary)

        market_impact = analytics.get("market_impact_summary", {})
        if market_impact:
            avg_impact = market_impact.get("average_impact", 0)
            table.add_row("Avg Market Impact", f"{avg_impact:.2f}")

        self.console.print(table)
        self.console.print()

    def _print_article_console(self, article: Article, index: int):
        """Print individual article to console."""
        # Sentiment emoji and color
        sentiment_emoji = {"positive": "🟢", "negative": "🔴", "neutral": "🟡"}.get(
            article.sentiment, "🟡"
        )
        sentiment_color = {
            "positive": "green",
            "negative": "red",
            "neutral": "yellow",
        }.get(article.sentiment, "yellow")

        # Market impact indicator
        impact_indicator = (
            "🔥"
            if article.market_impact_score and article.market_impact_score > 0.7
            else ""
        )

        # Create panel content
        content = [
            f"[bold cyan]{article.summarized_headline or article.title}[/bold cyan] {impact_indicator}",
            f"[dim]{article.source} • {article.published_at}[/dim]",
            f"[link={article.url}]{article.url}[/link]",
            "",
        ]

        # Add summary bullets
        content.extend(
            [f"[white]• {bullet}[/white]" for bullet in article.summary_bullets]
        )

        content.extend(
            ["", f"[magenta]💡 Why it matters: {article.why_it_matters}[/magenta]"]
        )

        # Add entities and topics if available
        if article.key_entities:
            entities_str = ", ".join(article.key_entities[:3])
            content.append(f"[dim]🏢 Key entities: {entities_str}[/dim]")

        if article.topics:
            topics_str = ", ".join(article.topics[:3])
            content.append(f"[dim]🏷️  Topics: {topics_str}[/dim]")

        # Sentiment and scores
        scores = []
        if article.sentiment_score is not None:
            scores.append(f"Sentiment: {article.sentiment_score:+.1f}")
        if article.market_impact_score is not None:
            scores.append(f"Impact: {article.market_impact_score:.1f}")

        if scores:
            content.append(f"[dim]📊 {' | '.join(scores)}[/dim]")

        # Create panel
        panel_title = f"{sentiment_emoji} Article {index}"
        panel = Panel(
            "\n".join(content),
            title=panel_title,
            title_align="left",
            border_style=sentiment_color,
            expand=False,
        )

        self.console.print(panel)
        self.console.print()

    async def output_to_markdown(self, articles: list[Article], analytics: dict) -> str:
        """Enhanced markdown output with analytics."""
        filepath = self.briefings_dir / f"{self.today}_enhanced.md"

        content_lines = [
            f"# 📈 Financial News Briefing • {self.today}",
            "",
            "## 📊 Analytics Summary",
            "",
        ]

        # Add analytics
        if analytics:
            content_lines.extend(self._format_analytics_markdown(analytics))

        content_lines.extend(["", f"## 📰 Top Stories ({len(articles)} articles)", ""])

        # Add articles
        for i, article in enumerate(articles, 1):
            content_lines.extend(self._format_article_markdown(article, i))

        # Add footer
        content_lines.extend(
            [
                "",
                "---",
                "",
                f"*Generated by Enhanced Financial News Summarizer on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
                f"*Powered by AI • {len(articles)} articles analyzed*",
            ]
        )

        # Write to file
        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write("\n".join(content_lines))

        logger.info(f"📄 Enhanced markdown report saved: {filepath}")
        return str(filepath)

    def _format_analytics_markdown(self, analytics: dict) -> list[str]:
        """Format analytics for markdown."""
        lines = []

        # Overall stats
        lines.append(f"- **Total Articles**: {analytics.get('total_articles', 0)}")

        # Sentiment analysis
        sentiment = analytics.get("sentiment_distribution", {})
        if sentiment:
            total = sum(sentiment.values())
            pos_pct = (sentiment.get("positive", 0) / total * 100) if total > 0 else 0
            neg_pct = (sentiment.get("negative", 0) / total * 100) if total > 0 else 0
            neu_pct = (sentiment.get("neutral", 0) / total * 100) if total > 0 else 0

            lines.extend(
                [
                    f"- **Sentiment Distribution**: 😊 {pos_pct:.1f}% | 😐 {neu_pct:.1f}% | 😟 {neg_pct:.1f}%",
                    f"- **Average Sentiment Score**: {analytics.get('sentiment_distribution', {}).get('average_score', 0):.2f}",
                ]
            )

        # Market impact
        market_impact = analytics.get("market_impact_summary", {})
        if market_impact:
            lines.append(
                f"- **Average Market Impact**: {market_impact.get('average_impact', 0):.2f}"
            )

        # Top entities
        top_entities = analytics.get("top_entities", [])[:5]
        if top_entities:
            entities_str = ", ".join(
                [f"{e['entity']} ({e['count']})" for e in top_entities]
            )
            lines.append(f"- **Top Entities**: {entities_str}")

        # Trending topics
        trending = analytics.get("trending_topics", [])[:5]
        if trending:
            topics_str = ", ".join([f"{t['topic']} ({t['count']})" for t in trending])
            lines.append(f"- **Trending Topics**: {topics_str}")

        return lines

    def _format_article_markdown(self, article: Article, index: int) -> list[str]:
        """Format individual article for markdown."""
        # Sentiment and impact indicators
        sentiment_emoji = {"positive": "🟢", "negative": "🔴", "neutral": "🟡"}.get(
            article.sentiment, "🟡"
        )
        impact_indicator = (
            " 🔥"
            if article.market_impact_score and article.market_impact_score > 0.7
            else ""
        )

        lines = [
            f"### {index}. [{article.summarized_headline or article.title}]({article.url}){impact_indicator}",
            "",
            f"**Source**: {article.source} • **Published**: {article.published_at}",
            f"**Sentiment**: {sentiment_emoji} {article.sentiment}",
            "",
        ]

        # Summary bullets
        lines.extend([f"- {bullet}" for bullet in article.summary_bullets])

        lines.extend(["", f"**💡 Why it matters**: {article.why_it_matters}", ""])

        # Additional metadata
        metadata = []
        if article.key_entities:
            metadata.append(f"**Entities**: {', '.join(article.key_entities[:5])}")

        if article.topics:
            metadata.append(f"**Topics**: {', '.join(article.topics[:5])}")

        if article.sentiment_score is not None:
            metadata.append(f"**Sentiment Score**: {article.sentiment_score:+.2f}")

        if article.market_impact_score is not None:
            metadata.append(f"**Market Impact**: {article.market_impact_score:.2f}")

        if metadata:
            lines.extend(metadata)
            lines.append("")

        lines.extend(["---", ""])

        return lines

    async def output_to_json(self, articles: list[Article], analytics: dict) -> str:
        """Output comprehensive JSON report."""
        filepath = self.briefings_dir / f"{self.today}_data.json"

        data = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_articles": len(articles),
                "version": "2.0",
            },
            "analytics": analytics,
            "articles": [article.to_dict() for article in articles],
        }

        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, indent=2, default=str))

        logger.info(f"📋 JSON data saved: {filepath}")
        return str(filepath)

    async def output_to_email(self, articles: list[Article]) -> bool:
        """Send enhanced email report."""
        # Email implementation would go here
        # Similar to original but with enhanced formatting
        logger.info("📧 Email output not yet implemented in enhanced version")
        return False


# Main enhanced application
async def run_enhanced_summarizer(
    queries: list[str],
    config_path: str = "config.yaml",
    max_articles: int | None = None,
):
    """Run the enhanced news summarizer."""

    # Initialize components
    config = Config(config_path)
    cache = CacheManager()
    console = Console()

    # Override max articles if specified
    if max_articles:
        config.config["processing"]["max_articles"] = max_articles

    # Validate API keys
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("❌ OPENAI_API_KEY is required")
        return

    start_time = time.time()

    async with aiohttp.ClientSession() as session:
        # Initialize components
        fetcher = EnhancedNewsFetcher(session, config, cache)
        summarizer = EnhancedNewsSummarizer(config, cache)
        analytics = NewsAnalytics()
        output_manager = EnhancedOutputManager(config, console)

        try:
            # Step 1: Fetch articles
            logger.info(f"🔍 Fetching news for: {', '.join(queries)}")
            articles = await fetcher.fetch_news(queries)

            if not articles:
                logger.warning("⚠️  No articles found")
                return

            # Limit articles
            max_articles_config = config.get("processing.max_articles", 25)
            articles = articles[:max_articles_config]

            # Step 2: Summarize with AI
            summarized_articles = await summarizer.summarize_articles(articles)

            # Step 3: Analyze
            logger.info("📊 Performing analytics...")
            analytics_results = analytics.analyze_articles(summarized_articles)

            # Step 4: Output
            logger.info("📤 Generating outputs...")
            output_results = await output_manager.output_all(
                summarized_articles, analytics_results
            )

            # Final summary
            elapsed = time.time() - start_time
            logger.info(f"✅ Process completed in {elapsed:.2f}s")
            logger.info(f"📈 Analyzed {len(summarized_articles)} articles")

            for output_type, result in output_results.items():
                if result:
                    logger.info(f"📄 {output_type.title()}: {result}")

        except Exception as e:
            logger.error(f"❌ Application error: {e}")
            raise


# CLI Interface
@click.command()
@click.option(
    "--queries",
    "-q",
    multiple=True,
    help="Stock tickers, keywords, or topics to search",
)
@click.option("--config", "-c", default="config.yaml", help="Configuration file path")
@click.option(
    "--max-articles", "-m", type=int, help="Maximum number of articles to process"
)
@click.option("--setup", is_flag=True, help="Run setup wizard")
def main(queries, config, max_articles, setup):
    """Enhanced Financial News Summarizer - AI-powered financial news analysis."""

    if setup:
        # Run setup
        import subprocess

        subprocess.run([sys.executable, "setup.py"])
        return

    # Load queries from config if not provided
    if not queries:
        try:
            config_obj = Config(config)
            queries = config_obj.get("queries", [])
        except Exception as e:
            click.echo(f"❌ Error loading config: {e}")
            return

    if not queries:
        click.echo("❌ No queries specified. Use --queries or configure in config.yaml")
        return

    # Run the enhanced summarizer
    try:
        asyncio.run(run_enhanced_summarizer(list(queries), config, max_articles))
    except KeyboardInterrupt:
        click.echo("\n⚠️  Process interrupted by user")
    except Exception as e:
        click.echo(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
