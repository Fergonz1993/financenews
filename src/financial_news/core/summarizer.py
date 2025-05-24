#!/usr/bin/env python3
"""
Enhanced Financial News Summarizer Agent
A production-ready AI-powered tool for financial news analysis with advanced features.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union
import hashlib
import re

# Core libraries
import aiohttp
import aiofiles
import dotenv
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, TaskID
from rich.table import Table
import click

# Data processing
import pandas as pd
import numpy as np
from textblob import TextBlob
from fuzzywuzzy import fuzz
import feedparser

# OpenAI and caching
from openai import AsyncOpenAI
import tiktoken
import cachetools
import redis

# Financial data sources
import finnhub
import requests

# Email and notifications
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Utilities
from tqdm.asyncio import tqdm
import colorlog
from asyncio_throttle import Throttler

# Load environment variables
dotenv.load_dotenv()

# Configure enhanced logging
def setup_logging():
    """Setup enhanced logging with colors."""
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    ))
    
    logger = logging.getLogger("enhanced_news_summarizer")
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', 'INFO')))
    return logger

logger = setup_logging()

# Enhanced configuration class
class Config:
    """Enhanced configuration management."""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"✅ Configuration loaded from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"❌ Error loading config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """Get default configuration if file is missing."""
        return {
            'queries': ['AAPL', 'MSFT', 'GOOGL'],
            'ai': {
                'model': 'gpt-4o-mini',
                'temperature': 0.3,
                'max_tokens': 500
            },
            'processing': {
                'max_articles': 25,
                'concurrent_requests': 5
            }
        }
    
    def _validate_config(self):
        """Validate configuration."""
        required_keys = ['queries', 'ai', 'processing']
        for key in required_keys:
            if key not in self.config:
                logger.warning(f"⚠️  Missing config section: {key}")
    
    def get(self, key: str, default=None):
        """Get configuration value with dot notation."""
        keys = key.split('.')
        value = self.config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

# Enhanced Article class with more metadata
class Article:
    """Enhanced article representation with additional metadata."""
    
    def __init__(self, title: str, url: str, source: str, published_at: str, content: str):
        self.id = hashlib.md5(f"{title}{url}".encode()).hexdigest()
        self.title = title
        self.url = url
        self.source = source
        self.published_at = published_at
        self.content = content
        
        # AI-generated fields
        self.summarized_headline: Optional[str] = None
        self.summary_bullets: List[str] = []
        self.why_it_matters: Optional[str] = None
        self.sentiment: Optional[str] = None
        self.sentiment_score: Optional[float] = None
        self.market_impact_score: Optional[float] = None
        self.relevance_score: Optional[float] = None
        self.key_entities: List[str] = []
        self.topics: List[str] = []
        
        # Metadata
        self.processed_at: Optional[datetime] = None
        self.processing_time: Optional[float] = None
        self.word_count: int = len(content.split()) if content else 0
        
    def __hash__(self) -> int:
        return hash(self.id)
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Article):
            return False
        return self.id == other.id
    
    def to_dict(self) -> Dict:
        """Convert article to dictionary for serialization."""
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'source': self.source,
            'published_at': self.published_at,
            'content': self.content,
            'summarized_headline': self.summarized_headline,
            'summary_bullets': self.summary_bullets,
            'why_it_matters': self.why_it_matters,
            'sentiment': self.sentiment,
            'sentiment_score': self.sentiment_score,
            'market_impact_score': self.market_impact_score,
            'relevance_score': self.relevance_score,
            'key_entities': self.key_entities,
            'topics': self.topics,
            'word_count': self.word_count,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }

# Enhanced caching system
class CacheManager:
    """Enhanced caching with Redis and memory fallback."""
    
    def __init__(self):
        self.redis_client = self._init_redis()
        self.memory_cache = cachetools.TTLCache(maxsize=1000, ttl=3600)
        self.cache_duration = 3600  # 1 hour default
    
    def _init_redis(self):
        """Initialize Redis client."""
        try:
            redis_url = os.getenv('REDIS_URL')
            if redis_url:
                client = redis.from_url(redis_url)
                client.ping()
                logger.info("✅ Redis cache connected")
                return client
        except Exception as e:
            logger.warning(f"⚠️  Redis not available, using memory cache: {e}")
        return None
    
    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        # Try Redis first
        if self.redis_client:
            try:
                value = self.redis_client.get(key)
                if value:
                    return value.decode('utf-8')
            except Exception as e:
                logger.warning(f"Redis get error: {e}")
        
        # Fallback to memory cache
        return self.memory_cache.get(key)
    
    async def set(self, key: str, value: str, ttl: Optional[int] = None):
        """Set value in cache."""
        ttl = ttl or self.cache_duration
        
        # Try Redis first
        if self.redis_client:
            try:
                self.redis_client.setex(key, ttl, value)
                return
            except Exception as e:
                logger.warning(f"Redis set error: {e}")
        
        # Fallback to memory cache
        self.memory_cache[key] = value

# Enhanced News Fetcher with multiple sources
class EnhancedNewsFetcher:
    """Enhanced news fetcher with multiple sources and better error handling."""
    
    def __init__(self, session: aiohttp.ClientSession, config: Config, cache: CacheManager):
        self.session = session
        self.config = config
        self.cache = cache
        self.throttler = Throttler(rate_limit=config.get('processing.concurrent_requests', 5))
        
        # API clients
        self.finnhub_client = self._init_finnhub()
        
        # Headers for web scraping
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def _init_finnhub(self):
        """Initialize Finnhub client."""
        api_key = os.getenv('FINNHUB_API_KEY')
        if api_key and api_key != 'your_finnhub_api_key_here':
            return finnhub.Client(api_key=api_key)
        return None
    
    async def fetch_from_newsapi(self, query: str) -> List[Article]:
        """Fetch from NewsAPI with caching and error handling."""
        api_key = os.getenv('NEWS_API_KEY')
        if not api_key or api_key == 'your_newsapi_key_here':
            logger.warning("NewsAPI key not configured")
            return []
        
        cache_key = f"newsapi:{query}:{datetime.now().strftime('%Y-%m-%d-%H')}"
        cached_result = await self.cache.get(cache_key)
        
        if cached_result:
            try:
                data = json.loads(cached_result)
                return [Article(**article) for article in data]
            except Exception as e:
                logger.warning(f"Cache parse error: {e}")
        
        async with self.throttler:
            try:
                url = "https://newsapi.org/v2/everything"
                params = {
                    "q": query,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": self.config.get('data_sources.newsapi.page_size', 50),
                    "apiKey": api_key,
                }
                
                async with self.session.get(url, params=params, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        articles = []
                        
                        for item in data.get("articles", []):
                            if self._should_include_article(item):
                                article = Article(
                                    title=item.get("title", ""),
                                    url=item.get("url", ""),
                                    source=item.get("source", {}).get("name", "NewsAPI"),
                                    published_at=item.get("publishedAt", ""),
                                    content=item.get("content", item.get("description", "")),
                                )
                                articles.append(article)
                        
                        # Cache the results
                        cache_data = [article.to_dict() for article in articles]
                        await self.cache.set(cache_key, json.dumps(cache_data, default=str))
                        
                        logger.info(f"✅ Fetched {len(articles)} articles from NewsAPI for '{query}'")
                        return articles
                    else:
                        logger.error(f"NewsAPI error: {response.status}")
                        return []
                        
            except Exception as e:
                logger.error(f"NewsAPI fetch error: {e}")
                return []
    
    def _should_include_article(self, article_data: Dict) -> bool:
        """Filter articles based on configuration."""
        # Check minimum content length
        content = article_data.get("content", "") or article_data.get("description", "")
        min_length = self.config.get('filters.min_article_length', 100)
        
        if len(content) < min_length:
            return False
        
        # Check exclude keywords
        exclude_keywords = self.config.get('filters.exclude_keywords', [])
        title = article_data.get("title", "").lower()
        content_lower = content.lower()
        
        for keyword in exclude_keywords:
            if keyword.lower() in title or keyword.lower() in content_lower:
                return False
        
        # Check article age
        max_age_hours = self.config.get('filters.max_age_hours', 48)
        published_at = article_data.get("publishedAt")
        
        if published_at:
            try:
                pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                if datetime.now().astimezone() - pub_date > timedelta(hours=max_age_hours):
                    return False
            except Exception:
                pass  # Skip date filtering if parsing fails
        
        return True
    
    async def fetch_from_rss_feeds(self, query: str) -> List[Article]:
        """Fetch from multiple RSS feeds."""
        articles = []
        
        rss_sources = {
            'Yahoo Finance': f'https://feeds.finance.yahoo.com/rss/2.0/headline?s={query}&region=US&lang=en-US',
            'MarketWatch': f'https://feeds.marketwatch.com/marketwatch/marketpulse/',
            'Reuters Business': 'http://feeds.reuters.com/reuters/businessNews',
            'Bloomberg': 'https://feeds.bloomberg.com/markets/news.rss'
        }
        
        for source_name, feed_url in rss_sources.items():
            if self.config.get(f'data_sources.rss_feeds.sources.{source_name.lower().replace(" ", "_")}.enabled', True):
                try:
                    articles.extend(await self._fetch_rss_feed(feed_url, source_name, query))
                except Exception as e:
                    logger.warning(f"RSS feed error for {source_name}: {e}")
        
        return articles
    
    async def _fetch_rss_feed(self, feed_url: str, source_name: str, query: str) -> List[Article]:
        """Fetch articles from a specific RSS feed."""
        try:
            # Use requests for RSS parsing (feedparser doesn't work well with aiohttp)
            response = requests.get(feed_url, headers=self.headers, timeout=10)
            feed = feedparser.parse(response.content)
            
            articles = []
            for entry in feed.entries[:10]:  # Limit per source
                # Check if article is relevant to query
                title = entry.get('title', '')
                content = entry.get('summary', entry.get('description', ''))
                
                if self._is_relevant_to_query(title + " " + content, query):
                    article = Article(
                        title=title,
                        url=entry.get('link', ''),
                        source=source_name,
                        published_at=entry.get('published', ''),
                        content=content,
                    )
                    articles.append(article)
            
            logger.info(f"✅ Fetched {len(articles)} relevant articles from {source_name}")
            return articles
            
        except Exception as e:
            logger.warning(f"RSS feed fetch error for {source_name}: {e}")
            return []
    
    def _is_relevant_to_query(self, text: str, query: str) -> bool:
        """Check if text is relevant to the query."""
        text_lower = text.lower()
        query_lower = query.lower()
        
        # Direct match
        if query_lower in text_lower:
            return True
        
        # For stock symbols, be more flexible
        if len(query) <= 5 and query.isupper():
            # Check for company name mentions, stock symbol variations
            variations = [query, f"${query}", f"{query} stock", f"{query} shares"]
            for variation in variations:
                if variation.lower() in text_lower:
                    return True
        
        return False
    
    async def fetch_news(self, queries: List[str]) -> List[Article]:
        """Fetch news from all sources for given queries."""
        all_articles = []
        
        with Progress() as progress:
            task = progress.add_task("Fetching news...", total=len(queries))
            
            for query in queries:
                progress.update(task, description=f"Fetching: {query}")
                
                # Fetch from different sources
                newsapi_articles = await self.fetch_from_newsapi(query)
                rss_articles = await self.fetch_from_rss_feeds(query)
                
                all_articles.extend(newsapi_articles)
                all_articles.extend(rss_articles)
                
                progress.advance(task)
        
        # Remove duplicates
        unique_articles = list(set(all_articles))
        logger.info(f"✅ Total unique articles: {len(unique_articles)}")
        
        return unique_articles

# Enhanced AI Summarizer
class EnhancedNewsSummarizer:
    """Enhanced AI summarizer with better prompts and error handling."""
    
    def __init__(self, config: Config, cache: CacheManager):
        self.config = config
        self.cache = cache
        self.client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = config.get('ai.model', 'gpt-4o-mini')
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.throttler = Throttler(rate_limit=60)  # OpenAI rate limit
    
    async def summarize_article(self, article: Article) -> Article:
        """Summarize article with enhanced AI analysis."""
        start_time = time.time()
        
        # Check cache first
        cache_key = f"summary:{article.id}:{self.model}"
        cached_result = await self.cache.get(cache_key)
        
        if cached_result:
            try:
                summary_data = json.loads(cached_result)
                self._populate_article_from_summary(article, summary_data)
                logger.debug(f"📋 Used cached summary for article: {article.title[:50]}...")
                return article
            except Exception as e:
                logger.warning(f"Cache parse error: {e}")
        
        async with self.throttler:
            try:
                # Prepare content
                content = self._prepare_content(article)
                
                # Enhanced prompt
                prompt = self._create_enhanced_prompt(content)
                
                # Call OpenAI API
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.config.get('ai.temperature', 0.3),
                    max_tokens=self.config.get('ai.max_tokens', 500),
                    response_format={"type": "json_object"}
                )
                
                # Parse response
                content_str = response.choices[0].message.content
                summary_data = json.loads(content_str)
                
                # Populate article
                self._populate_article_from_summary(article, summary_data)
                
                # Cache the result
                await self.cache.set(cache_key, json.dumps(summary_data))
                
                # Track processing time
                article.processing_time = time.time() - start_time
                article.processed_at = datetime.now()
                
                logger.debug(f"✅ Summarized: {article.title[:50]}...")
                return article
                
            except Exception as e:
                logger.error(f"❌ Summarization error: {e}")
                self._populate_fallback_summary(article)
                return article
    
    def _prepare_content(self, article: Article) -> str:
        """Prepare and truncate content for AI processing."""
        content = article.content or ""
        
        # Truncate to fit token limits
        max_tokens = 3000
        tokens = self.tokenizer.encode(content)
        
        if len(tokens) > max_tokens:
            truncated_tokens = tokens[:max_tokens]
            content = self.tokenizer.decode(truncated_tokens)
        
        return content
    
    def _create_enhanced_prompt(self, content: str) -> str:
        """Create enhanced prompt for AI summarization."""
        return f"""You are an expert financial analyst. Analyze this financial news article and provide a comprehensive summary.

Article Content:
{content}

Provide your analysis in JSON format with these exact fields:
{{
    "headline": "A compelling, concise headline that captures the essence",
    "summary_bullets": ["3-5 key bullet points about the main developments"],
    "why_it_matters": "Clear explanation of market/investment implications",
    "sentiment": "positive, negative, or neutral",
    "sentiment_score": -1.0 to 1.0 (very negative to very positive),
    "market_impact_score": 0.0 to 1.0 (no impact to major market impact),
    "key_entities": ["relevant companies, people, or financial instruments"],
    "topics": ["relevant financial topics or themes"]
}}

Guidelines:
- Focus on financial implications and market impact
- Use clear, professional language
- Highlight actionable insights
- Consider both short-term and long-term implications"""
    
    def _populate_article_from_summary(self, article: Article, summary_data: Dict):
        """Populate article with summary data."""
        article.summarized_headline = summary_data.get("headline", article.title)
        article.summary_bullets = summary_data.get("summary_bullets", [])
        article.why_it_matters = summary_data.get("why_it_matters", "")
        article.sentiment = summary_data.get("sentiment", "neutral")
        article.sentiment_score = float(summary_data.get("sentiment_score", 0.0))
        article.market_impact_score = float(summary_data.get("market_impact_score", 0.0))
        article.key_entities = summary_data.get("key_entities", [])
        article.topics = summary_data.get("topics", [])
    
    def _populate_fallback_summary(self, article: Article):
        """Populate article with fallback summary when AI fails."""
        article.summarized_headline = article.title
        article.summary_bullets = ["[Summary unavailable due to API error]"]
        article.why_it_matters = "Unable to analyze due to technical issues."
        article.sentiment = "neutral"
        article.sentiment_score = 0.0
        article.market_impact_score = 0.0
        article.key_entities = []
        article.topics = []
    
    async def summarize_articles(self, articles: List[Article]) -> List[Article]:
        """Summarize multiple articles with progress tracking."""
        logger.info(f"🤖 Starting AI summarization of {len(articles)} articles")
        
        # Use tqdm for async progress bar
        summarized = []
        async for article in tqdm.as_completed(
            [self.summarize_article(article) for article in articles],
            desc="Summarizing articles"
        ):
            summarized.append(await article)
        
        # Sort by market impact score and sentiment
        summarized.sort(key=lambda x: (x.market_impact_score or 0, abs(x.sentiment_score or 0)), reverse=True)
        
        logger.info("✅ Summarization complete")
        return summarized

# Continue with the rest of the enhanced components...

# Enhanced Analytics
class NewsAnalytics:
    """Advanced analytics for news data."""
    
    def __init__(self):
        self.df = None
    
    def analyze_articles(self, articles: List[Article]) -> Dict:
        """Perform comprehensive analysis on articles."""
        if not articles:
            return {}
        
        # Convert to DataFrame for analysis
        data = [article.to_dict() for article in articles]
        self.df = pd.DataFrame(data)
        
        analytics = {
            'total_articles': len(articles),
            'sentiment_distribution': self._analyze_sentiment(),
            'source_distribution': self._analyze_sources(),
            'top_entities': self._analyze_entities(articles),
            'trending_topics': self._analyze_topics(articles),
            'market_impact_summary': self._analyze_market_impact(),
            'processing_stats': self._analyze_processing_stats(),
        }
        
        return analytics
    
    def _analyze_sentiment(self) -> Dict:
        """Analyze sentiment distribution."""
        if 'sentiment' not in self.df.columns:
            return {}
        
        sentiment_counts = self.df['sentiment'].value_counts()
        avg_sentiment_score = self.df['sentiment_score'].mean()
        
        return {
            'distribution': sentiment_counts.to_dict(),
            'average_score': float(avg_sentiment_score) if not pd.isna(avg_sentiment_score) else 0.0,
            'positive_ratio': len(self.df[self.df['sentiment'] == 'positive']) / len(self.df),
            'negative_ratio': len(self.df[self.df['sentiment'] == 'negative']) / len(self.df)
        }
    
    def _analyze_sources(self) -> Dict:
        """Analyze source distribution."""
        source_counts = self.df['source'].value_counts()
        return {
            'distribution': source_counts.to_dict(),
            'total_sources': len(source_counts),
            'top_source': source_counts.index[0] if len(source_counts) > 0 else None
        }
    
    def _analyze_entities(self, articles: List[Article]) -> List[Dict]:
        """Analyze key entities mentioned."""
        entity_counts = {}
        
        for article in articles:
            for entity in article.key_entities:
                entity_counts[entity] = entity_counts.get(entity, 0) + 1
        
        # Sort by frequency
        sorted_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [{'entity': entity, 'count': count} for entity, count in sorted_entities[:10]]
    
    def _analyze_topics(self, articles: List[Article]) -> List[Dict]:
        """Analyze trending topics."""
        topic_counts = {}
        
        for article in articles:
            for topic in article.topics:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        # Sort by frequency
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [{'topic': topic, 'count': count} for topic, count in sorted_topics[:10]]
    
    def _analyze_market_impact(self) -> Dict:
        """Analyze market impact scores."""
        if 'market_impact_score' not in self.df.columns:
            return {}
        
        return {
            'average_impact': float(self.df['market_impact_score'].mean()),
            'high_impact_count': len(self.df[self.df['market_impact_score'] > 0.7]),
            'low_impact_count': len(self.df[self.df['market_impact_score'] < 0.3])
        }
    
    def _analyze_processing_stats(self) -> Dict:
        """Analyze processing performance."""
        if 'processing_time' not in self.df.columns:
            return {}
        
        processing_times = self.df['processing_time'].dropna()
        
        return {
            'average_processing_time': float(processing_times.mean()) if len(processing_times) > 0 else 0,
            'total_processing_time': float(processing_times.sum()) if len(processing_times) > 0 else 0,
            'articles_processed': len(processing_times)
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
    
    async def output_all(self, articles: List[Article], analytics: Dict):
        """Output to all configured destinations."""
        results = {}
        
        if self.config.get('output.console', True):
            self.output_to_console(articles, analytics)
            results['console'] = True
        
        if self.config.get('output.markdown', True):
            md_path = await self.output_to_markdown(articles, analytics)
            results['markdown'] = md_path
        
        if self.config.get('output.json', False):
            json_path = await self.output_to_json(articles, analytics)
            results['json'] = json_path
        
        if self.config.get('output.email', False):
            email_sent = await self.output_to_email(articles)
            results['email'] = email_sent
        
        return results
    
    def output_to_console(self, articles: List[Article], analytics: Dict):
        """Enhanced console output with analytics."""
        # Header
        self.console.print(f"\n[bold green]📈 Financial News Briefing • {self.today}[/bold green]")
        
        # Analytics summary
        if analytics:
            self._print_analytics_summary(analytics)
        
        # Articles
        self.console.print(f"\n[bold cyan]📰 Top Stories ({len(articles)} articles)[/bold cyan]\n")
        
        for i, article in enumerate(articles, 1):
            self._print_article_console(article, i)
    
    def _print_analytics_summary(self, analytics: Dict):
        """Print analytics summary to console."""
        table = Table(title="📊 Analytics Summary", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="yellow")
        
        # Add key metrics
        table.add_row("Total Articles", str(analytics.get('total_articles', 0)))
        
        sentiment = analytics.get('sentiment_distribution', {})
        if sentiment:
            sentiment_summary = f"😊 {sentiment.get('positive', 0)} | 😐 {sentiment.get('neutral', 0)} | 😟 {sentiment.get('negative', 0)}"
            table.add_row("Sentiment", sentiment_summary)
        
        market_impact = analytics.get('market_impact_summary', {})
        if market_impact:
            avg_impact = market_impact.get('average_impact', 0)
            table.add_row("Avg Market Impact", f"{avg_impact:.2f}")
        
        self.console.print(table)
        self.console.print()
    
    def _print_article_console(self, article: Article, index: int):
        """Print individual article to console."""
        # Sentiment emoji and color
        sentiment_emoji = {"positive": "🟢", "negative": "🔴", "neutral": "🟡"}.get(article.sentiment, "🟡")
        sentiment_color = {"positive": "green", "negative": "red", "neutral": "yellow"}.get(article.sentiment, "yellow")
        
        # Market impact indicator
        impact_indicator = "🔥" if article.market_impact_score and article.market_impact_score > 0.7 else ""
        
        # Create panel content
        content = [
            f"[bold cyan]{article.summarized_headline or article.title}[/bold cyan] {impact_indicator}",
            f"[dim]{article.source} • {article.published_at}[/dim]",
            f"[link={article.url}]{article.url}[/link]",
            ""
        ]
        
        # Add summary bullets
        for bullet in article.summary_bullets:
            content.append(f"[white]• {bullet}[/white]")
        
        content.extend([
            "",
            f"[magenta]💡 Why it matters: {article.why_it_matters}[/magenta]"
        ])
        
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
            expand=False
        )
        
        self.console.print(panel)
        self.console.print()
    
    async def output_to_markdown(self, articles: List[Article], analytics: Dict) -> str:
        """Enhanced markdown output with analytics."""
        filepath = self.briefings_dir / f"{self.today}_enhanced.md"
        
        content_lines = [
            f"# 📈 Financial News Briefing • {self.today}",
            "",
            "## 📊 Analytics Summary",
            ""
        ]
        
        # Add analytics
        if analytics:
            content_lines.extend(self._format_analytics_markdown(analytics))
        
        content_lines.extend([
            "",
            f"## 📰 Top Stories ({len(articles)} articles)",
            ""
        ])
        
        # Add articles
        for i, article in enumerate(articles, 1):
            content_lines.extend(self._format_article_markdown(article, i))
        
        # Add footer
        content_lines.extend([
            "",
            "---",
            "",
            f"*Generated by Enhanced Financial News Summarizer on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            f"*Powered by AI • {len(articles)} articles analyzed*"
        ])
        
        # Write to file
        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write("\n".join(content_lines))
        
        logger.info(f"📄 Enhanced markdown report saved: {filepath}")
        return str(filepath)
    
    def _format_analytics_markdown(self, analytics: Dict) -> List[str]:
        """Format analytics for markdown."""
        lines = []
        
        # Overall stats
        lines.append(f"- **Total Articles**: {analytics.get('total_articles', 0)}")
        
        # Sentiment analysis
        sentiment = analytics.get('sentiment_distribution', {})
        if sentiment:
            total = sum(sentiment.values())
            pos_pct = (sentiment.get('positive', 0) / total * 100) if total > 0 else 0
            neg_pct = (sentiment.get('negative', 0) / total * 100) if total > 0 else 0
            neu_pct = (sentiment.get('neutral', 0) / total * 100) if total > 0 else 0
            
            lines.extend([
                f"- **Sentiment Distribution**: 😊 {pos_pct:.1f}% | 😐 {neu_pct:.1f}% | 😟 {neg_pct:.1f}%",
                f"- **Average Sentiment Score**: {analytics.get('sentiment_distribution', {}).get('average_score', 0):.2f}"
            ])
        
        # Market impact
        market_impact = analytics.get('market_impact_summary', {})
        if market_impact:
            lines.append(f"- **Average Market Impact**: {market_impact.get('average_impact', 0):.2f}")
        
        # Top entities
        top_entities = analytics.get('top_entities', [])[:5]
        if top_entities:
            entities_str = ", ".join([f"{e['entity']} ({e['count']})" for e in top_entities])
            lines.append(f"- **Top Entities**: {entities_str}")
        
        # Trending topics
        trending = analytics.get('trending_topics', [])[:5]
        if trending:
            topics_str = ", ".join([f"{t['topic']} ({t['count']})" for t in trending])
            lines.append(f"- **Trending Topics**: {topics_str}")
        
        return lines
    
    def _format_article_markdown(self, article: Article, index: int) -> List[str]:
        """Format individual article for markdown."""
        # Sentiment and impact indicators
        sentiment_emoji = {"positive": "🟢", "negative": "🔴", "neutral": "🟡"}.get(article.sentiment, "🟡")
        impact_indicator = " 🔥" if article.market_impact_score and article.market_impact_score > 0.7 else ""
        
        lines = [
            f"### {index}. [{article.summarized_headline or article.title}]({article.url}){impact_indicator}",
            "",
            f"**Source**: {article.source} • **Published**: {article.published_at}",
            f"**Sentiment**: {sentiment_emoji} {article.sentiment}",
            ""
        ]
        
        # Summary bullets
        for bullet in article.summary_bullets:
            lines.append(f"- {bullet}")
        
        lines.extend([
            "",
            f"**💡 Why it matters**: {article.why_it_matters}",
            ""
        ])
        
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
    
    async def output_to_json(self, articles: List[Article], analytics: Dict) -> str:
        """Output comprehensive JSON report."""
        filepath = self.briefings_dir / f"{self.today}_data.json"
        
        data = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_articles': len(articles),
                'version': '2.0'
            },
            'analytics': analytics,
            'articles': [article.to_dict() for article in articles]
        }
        
        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, indent=2, default=str))
        
        logger.info(f"📋 JSON data saved: {filepath}")
        return str(filepath)
    
    async def output_to_email(self, articles: List[Article]) -> bool:
        """Send enhanced email report."""
        # Email implementation would go here
        # Similar to original but with enhanced formatting
        logger.info("📧 Email output not yet implemented in enhanced version")
        return False

# Main enhanced application
async def run_enhanced_summarizer(
    queries: List[str],
    config_path: str = "config.yaml",
    max_articles: Optional[int] = None
):
    """Run the enhanced news summarizer."""
    
    # Initialize components
    config = Config(config_path)
    cache = CacheManager()
    console = Console()
    
    # Override max articles if specified
    if max_articles:
        config.config['processing']['max_articles'] = max_articles
    
    # Validate API keys
    if not os.getenv('OPENAI_API_KEY'):
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
            max_articles_config = config.get('processing.max_articles', 25)
            articles = articles[:max_articles_config]
            
            # Step 2: Summarize with AI
            summarized_articles = await summarizer.summarize_articles(articles)
            
            # Step 3: Analyze
            logger.info("📊 Performing analytics...")
            analytics_results = analytics.analyze_articles(summarized_articles)
            
            # Step 4: Output
            logger.info("📤 Generating outputs...")
            output_results = await output_manager.output_all(summarized_articles, analytics_results)
            
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
@click.option('--queries', '-q', multiple=True, help='Stock tickers, keywords, or topics to search')
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
@click.option('--max-articles', '-m', type=int, help='Maximum number of articles to process')
@click.option('--setup', is_flag=True, help='Run setup wizard')
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
            queries = config_obj.get('queries', [])
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