#!/usr/bin/env python3
# news_summarizer.py - Financial News Summarizer Agent
# A production-ready CLI tool that fetches, summarizes and delivers financial news

import argparse
import asyncio
import feedparser
import finnhub
import json
import logging
import os
import re
import smtplib
import sys
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

import aiohttp
import dotenv
import openai
import tiktoken
from rich.console import Console
from rich.panel import Panel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("news_summarizer")

# Load environment variables
dotenv.load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_SERVER = os.getenv("EMAIL_SERVER", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))

# Initialize OpenAI client
openai.api_key = OPENAI_API_KEY

# Initialize Finnhub client if API key is available
finnhub_client = None
if FINNHUB_API_KEY and FINNHUB_API_KEY != "your_finnhub_api_key_here":
    finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)

# Check if required API keys are available
USE_NEWSAPI = NEWS_API_KEY and NEWS_API_KEY != "your_newsapi_key_here"
USE_FINNHUB = finnhub_client is not None

# Initialize Rich console
console = Console()

# Token counter for OpenAI API
tokenizer = tiktoken.get_encoding("cl100k_base")  # GPT-4 tokenizer


class Article:
    """Represents a news article with original and summarized content."""

    def __init__(
        self,
        title: str,
        url: str,
        source: str,
        published_at: str,
        content: str,
    ):
        self.title = title
        self.url = url
        self.source = source
        self.published_at = published_at
        self.content = content
        self.summarized_headline: Optional[str] = None
        self.summary_bullets: List[str] = []
        self.why_it_matters: Optional[str] = None
        self.sentiment: Optional[str] = None
        self.sentiment_score: Optional[float] = None

    def __hash__(self) -> int:
        """Enable deduplication by hashing on title and URL."""
        return hash((self.title.lower(), self.url))

    def __eq__(self, other) -> bool:
        """Articles are equal if they have the same URL or very similar titles."""
        if not isinstance(other, Article):
            return False

        # URLs match
        if self.url == other.url:
            return True

        # Or very similar titles (simple fuzzy match)
        title1 = re.sub(r"[^\w\s]", "", self.title.lower())
        title2 = re.sub(r"[^\w\s]", "", other.title.lower())
        if (
            len(title1) > 20
            and len(title2) > 20
            and (title1 in title2 or title2 in title1)
        ):
            return True

        return False


class NewsFetcher:
    """Handles fetching news from various sources."""

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.rate_limiter = asyncio.Semaphore(1)  # Limit to 1 request per second
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0'
        }
        self.finnhub_client = finnhub_client

    async def fetch_from_newsapi(
        self, query: str, page_size: int = 100
    ) -> List[Article]:
        """Fetch news articles from NewsAPI based on query."""
        # Skip if NewsAPI key is not configured
        if not USE_NEWSAPI:
            logger.warning("NewsAPI key not configured, skipping NewsAPI source")
            return []
            
        async with self.rate_limiter:
            try:
                url = "https://newsapi.org/v2/everything"
                params = {
                    "q": query,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": page_size,
                    "apiKey": NEWS_API_KEY,
                }
                async with self.session.get(url, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"NewsAPI error: {error_text}")
                        return []

                    data = await response.json()
                    articles = []
                    for item in data.get("articles", []):
                        article = Article(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            source=item.get("source", {}).get("name", "Unknown"),
                            published_at=item.get("publishedAt", ""),
                            content=item.get("content", item.get("description", "")),
                        )
                        articles.append(article)
                    return articles
            except Exception as e:
                logger.error(f"Error fetching from NewsAPI: {e}")
                return []
            finally:
                # Rate limiting
                await asyncio.sleep(1.0)

    async def fetch_from_rss_feed(self, feed_url: str, source_name: str) -> List[Article]:
        """Generic method to fetch articles from any RSS feed."""
        try:
            # Parse the RSS feed
            news_feed = feedparser.parse(feed_url)
            
            articles = []
            for entry in news_feed.entries:
                # Extract the relevant information
                title = entry.get('title', '')
                url = entry.get('link', '')
                published_at = entry.get('published', '')
                
                # Try different content fields that might be available
                content = ''
                if 'summary' in entry:
                    content = entry.get('summary', '')
                elif 'description' in entry:
                    content = entry.get('description', '')
                elif 'content' in entry:
                    if isinstance(entry.content, list) and len(entry.content) > 0:
                        content = entry.content[0].get('value', '')
                
                article = Article(
                    title=title,
                    url=url,
                    source=source_name,
                    published_at=published_at,
                    content=content,
                )
                articles.append(article)
                
            return articles
        except Exception as e:
            logger.error(f"Error fetching from RSS feed {feed_url}: {e}")
            return []

    async def fetch_from_yahoo_finance_rss(self, query: str) -> List[Article]:
        """Fetch news articles from Yahoo Finance RSS based on query."""
        try:
            # Format query for Yahoo Finance RSS
            # If query looks like a ticker, use it directly; otherwise, skip
            if re.match(r'^[A-Za-z]+$', query) or re.match(r'^[A-Za-z]+\.[A-Za-z]+$', query):
                ticker = query
                rss_feed_url = f'https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US'
                return await self.fetch_from_rss_feed(rss_feed_url, "Yahoo Finance")
            elif query == "market":  # Special case for general market news
                rss_feed_url = 'https://finance.yahoo.com/news/rssindex'
                return await self.fetch_from_rss_feed(rss_feed_url, "Yahoo Finance")
            else:
                # Skip non-ticker queries for Yahoo Finance
                return []
        except Exception as e:
            logger.error(f"Error fetching from Yahoo Finance RSS: {e}")
            return []
            
    async def fetch_from_cnbc_rss(self, query: str) -> List[Article]:
        """Fetch news articles from CNBC RSS feeds."""
        try:
            all_articles = []
            
            # Map of CNBC RSS feeds by category
            cnbc_feeds = {
                "market": [
                    "https://www.cnbc.com/id/20409666/device/rss/rss.html", # Market Insider
                    "https://www.cnbc.com/id/15839069/device/rss/rss.html"  # Investing
                ],
                "finance": [
                    "https://www.cnbc.com/id/10000664/device/rss/rss.html"  # Finance
                ],
                "business": [
                    "https://www.cnbc.com/id/10001147/device/rss/rss.html"  # Business News
                ],
                "economy": [
                    "https://www.cnbc.com/id/20910258/device/rss/rss.html"  # Economy
                ],
                "earnings": [
                    "https://www.cnbc.com/id/15839135/device/rss/rss.html"  # Earnings
                ],
                "investing": [
                    "https://www.cnbc.com/id/15839069/device/rss/rss.html"  # Investing
                ]
            }
            
            # Select feeds based on query
            feeds_to_fetch = []
            
            # For ticker symbols, use market and investing feeds
            if re.match(r'^[A-Za-z]+$', query) or re.match(r'^[A-Za-z]+\.[A-Za-z]+$', query):
                feeds_to_fetch.extend(cnbc_feeds.get("market", []))
                feeds_to_fetch.extend(cnbc_feeds.get("investing", []))
            # For market query, use market and business feeds
            elif query == "market":
                feeds_to_fetch.extend(cnbc_feeds.get("market", []))
                feeds_to_fetch.extend(cnbc_feeds.get("business", []))
                feeds_to_fetch.extend(cnbc_feeds.get("economy", []))
            # For categorized queries, use matching feeds if available
            elif query.lower() in cnbc_feeds:
                feeds_to_fetch.extend(cnbc_feeds.get(query.lower(), []))
                
            # Fetch articles from selected feeds
            for feed_url in feeds_to_fetch:
                articles = await self.fetch_from_rss_feed(feed_url, "CNBC")
                all_articles.extend(articles)
                
            return all_articles
        except Exception as e:
            logger.error(f"Error fetching from CNBC RSS: {e}")
            return []
            
    async def fetch_from_seeking_alpha_rss(self, query: str) -> List[Article]:
        """Fetch news articles from Seeking Alpha RSS feeds."""
        try:
            # Seeking Alpha has different RSS feeds for different content
            seeking_alpha_base_url = "https://seekingalpha.com/feed"
            
            if query == "market":
                # Market news feed
                feed_url = f"{seeking_alpha_base_url}/news/market"
                return await self.fetch_from_rss_feed(feed_url, "Seeking Alpha")
            elif re.match(r'^[A-Za-z]+$', query) or re.match(r'^[A-Za-z]+\.[A-Za-z]+$', query):
                # Ticker-specific feed - only works for some major tickers
                feed_url = f"{seeking_alpha_base_url}/stock/{query.upper()}"
                return await self.fetch_from_rss_feed(feed_url, "Seeking Alpha")
            else:
                return []
        except Exception as e:
            logger.error(f"Error fetching from Seeking Alpha RSS: {e}")
            return []
            
    async def fetch_from_marketwatch_rss(self, query: str) -> List[Article]:
        """Fetch news articles from MarketWatch RSS feeds."""
        try:
            all_articles = []
            
            # MarketWatch RSS feeds by category
            if query == "market" or query == "investing":
                # Top Stories feed
                feed_url = "https://feeds.marketwatch.com/marketwatch/topstories/"
                articles = await self.fetch_from_rss_feed(feed_url, "MarketWatch")
                all_articles.extend(articles)
                
                # MarketPulse feed (real-time updates)
                feed_url = "https://feeds.marketwatch.com/marketwatch/marketpulse/"
                articles = await self.fetch_from_rss_feed(feed_url, "MarketWatch")
                all_articles.extend(articles)
                
            return all_articles
        except Exception as e:
            logger.error(f"Error fetching from MarketWatch RSS: {e}")
            return []
            
    async def fetch_from_finnhub(self, query: str) -> List[Article]:
        """Fetch news articles from Finnhub API based on query."""
        if not USE_FINNHUB:
            logger.warning("Finnhub API key not configured, skipping Finnhub source")
            return []
            
        try:
            # Use the rate limiter to respect Finnhub's API rate limits
            async with self.rate_limiter:
                articles = []
                
                # Calculate date range (last 7 days)
                today = datetime.now()
                from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
                to_date = today.strftime("%Y-%m-%d")
                
                # For tickers, use company_news endpoint
                if re.match(r'^[A-Za-z]+$', query) or re.match(r'^[A-Za-z]+\.[A-Za-z]+$', query):
                    # Use Finnhub's company news endpoint
                    news_data = self.finnhub_client.company_news(query, _from=from_date, to=to_date)
                    
                    for item in news_data:
                        title = item.get("headline", "")
                        url = item.get("url", "")
                        source = item.get("source", "Finnhub")
                        timestamp = item.get("datetime", 0)
                        if timestamp > 0:
                            published_at = datetime.fromtimestamp(timestamp).strftime("%a, %d %b %Y %H:%M:%S +0000")
                        else:
                            published_at = ""
                        summary = item.get("summary", "")
                        
                        article = Article(
                            title=title,
                            url=url,
                            source=source,
                            published_at=published_at,
                            content=summary,
                        )
                        articles.append(article)
                elif query == "market":
                    # Get general market news for "market" query
                    news_data = self.finnhub_client.general_news("general", min_id=0)
                    
                    for item in news_data:
                        title = item.get("headline", "")
                        url = item.get("url", "")
                        source = item.get("source", "Finnhub")
                        timestamp = item.get("datetime", 0)
                        if timestamp > 0:
                            published_at = datetime.fromtimestamp(timestamp).strftime("%a, %d %b %Y %H:%M:%S +0000")
                        else:
                            published_at = ""
                        summary = item.get("summary", "")
                        
                        article = Article(
                            title=title,
                            url=url,
                            source=source,
                            published_at=published_at,
                            content=summary,
                        )
                        articles.append(article)
                else:
                    # Skip non-ticker, non-market queries
                    pass
                    
                await asyncio.sleep(1.0)  # Rate limiting
                return articles
                
        except Exception as e:
            logger.error(f"Error fetching from Finnhub API: {e}")
            return []

    async def fetch_news(self, queries: List[str]) -> List[Article]:
        """Fetch news from all sources based on queries."""
        all_articles: Set[Article] = set()
        
        # Add a special query for general market news
        all_queries = queries.copy()
        if "market" not in all_queries:
            all_queries.append("market")
        
        # Add some financial categories that might be useful
        financial_categories = ["finance", "investing", "business", "economy", "earnings"]
        for category in financial_categories:
            if category not in all_queries:
                all_queries.append(category)
        
        # Track if we have any sources configured
        sources_available = USE_NEWSAPI or USE_FINNHUB or True  # RSS feeds are always available
        if not sources_available:
            logger.error("No news sources configured. Check your API keys.")
            
        for query in all_queries:
            # First try all the free RSS feed sources
            yahoo_articles = await self.fetch_from_yahoo_finance_rss(query)
            all_articles.update(yahoo_articles)
            
            cnbc_articles = await self.fetch_from_cnbc_rss(query)
            all_articles.update(cnbc_articles)
            
            seeking_alpha_articles = await self.fetch_from_seeking_alpha_rss(query)
            all_articles.update(seeking_alpha_articles)
            
            marketwatch_articles = await self.fetch_from_marketwatch_rss(query)
            all_articles.update(marketwatch_articles)
            
            # Then try paid API sources if configured
            if USE_NEWSAPI:
                newsapi_articles = await self.fetch_from_newsapi(query)
                all_articles.update(newsapi_articles)
                
            if USE_FINNHUB:
                finnhub_articles = await self.fetch_from_finnhub(query)
                all_articles.update(finnhub_articles)

        # Convert to list and sort by published date (descending)
        return sorted(
            list(all_articles),
            key=lambda x: x.published_at if x.published_at else "",
            reverse=True,
        )


class NewsSummarizer:
    """Handles summarizing news articles using OpenAI API."""

    def __init__(self, model: str = "gpt-3.5-turbo"):
        self.model = model
        self.rate_limiter = asyncio.Semaphore(1)  # Limit to 1 request per second

    def _truncate_text(self, text: str, max_tokens: int = 3000) -> str:
        """Truncate text to fit within token limit."""
        tokens = tokenizer.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return tokenizer.decode(tokens[:max_tokens]) + "..."

    async def summarize_article(self, article: Article) -> Article:
        """Summarize a news article using OpenAI API."""
        async with self.rate_limiter:
            try:
                truncated_text = self._truncate_text(article.content)
                prompt = f"""You are a top-tier financial journalist. Summarize the following article for a busy investment banker:
{truncated_text}
Return JSON with keys: "headline", "summary_bullets", "why_it_matters", "sentiment", "sentiment_score".

For sentiment, use one of: "positive", "negative", "neutral".
For sentiment_score, use a scale from -1.0 (very negative) to 1.0 (very positive), with 0.0 being neutral."""

                response = await openai.ChatCompletion.acreate(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                    max_tokens=350,
                )

                # Parse the response
                content = response.choices[0].message.content.strip()
                
                # Handle different response formats
                try:
                    # Try to parse as JSON
                    summary_data = json.loads(content)
                    article.summarized_headline = summary_data.get("headline", "")
                    article.summary_bullets = summary_data.get("summary_bullets", [])
                    article.sentiment = summary_data.get("sentiment", "neutral")
                    article.sentiment_score = summary_data.get("sentiment_score", 0.0)
                    if isinstance(article.summary_bullets, str):
                        # Handle if bullets are returned as a string
                        article.summary_bullets = [
                            b.strip() for b in article.summary_bullets.split("\n") if b.strip()
                        ]
                    article.why_it_matters = summary_data.get("why_it_matters", "")
                except json.JSONDecodeError:
                    # Fallback parsing for non-JSON responses
                    lines = content.split("\n")
                    for i, line in enumerate(lines):
                        if "headline:" in line.lower():
                            article.summarized_headline = line.split(":", 1)[1].strip()
                        elif "summary" in line.lower() and i+1 < len(lines):
                            # Collect bullet points
                            bullets = []
                            j = i+1
                            while j < len(lines) and lines[j].strip().startswith(("-", "•", "*")):
                                bullets.append(lines[j].strip()[1:].strip())
                                j += 1
                            article.summary_bullets = bullets
                        elif "why it matters:" in line.lower():
                            article.why_it_matters = line.split(":", 1)[1].strip()
                
                return article
            except Exception as e:
                logger.error(f"Error summarizing article: {e}")
                article.summarized_headline = article.title
                article.summary_bullets = ["[Summary unavailable due to API error]"]
                article.why_it_matters = "Unable to analyze due to technical issues."
                return article
            finally:
                # Rate limiting
                await asyncio.sleep(1.0)

    async def summarize_articles(self, articles: List[Article]) -> List[Article]:
        """Summarize multiple articles concurrently."""
        tasks = [self.summarize_article(article) for article in articles]
        return await asyncio.gather(*tasks)


class NewsOutputter:
    """Handles outputting news summaries in various formats."""

    def __init__(self, console: Console):
        self.console = console
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.briefings_dir = Path("./briefings")
        self.briefings_dir.mkdir(exist_ok=True)

    def _format_article_markdown(self, article: Article) -> str:
        """Format an article for markdown output."""
        # Add sentiment emoji based on sentiment
        sentiment_emoji = "🟡" # neutral/yellow circle
        if article.sentiment == "positive":
            sentiment_emoji = "🟢" # green circle
        elif article.sentiment == "negative":
            sentiment_emoji = "🔴" # red circle
        
        sentiment_info = ""
        if article.sentiment:
            score = f" ({article.sentiment_score:.1f})" if article.sentiment_score is not None else ""
            sentiment_info = f" {sentiment_emoji} **{article.sentiment.upper()}**{score}"
            
        md = f"## [{article.summarized_headline or article.title}]({article.url}){sentiment_info}\n"
        md += f"*Source: {article.source}*\n\n"
        for bullet in article.summary_bullets:
            md += f"* {bullet}\n"
        md += f"\n**Why it matters:** {article.why_it_matters}\n\n"
        md += f"*Published: {article.published_at}*\n\n---\n\n"
        return md

    def _format_article_console(self, article: Article) -> None:
        """Format an article for console output with colors."""
        # Set sentiment color
        sentiment_color = "yellow"
        if article.sentiment == "positive":
            sentiment_color = "green"
        elif article.sentiment == "negative":
            sentiment_color = "red"
            
        sentiment_display = ""
        if article.sentiment:
            score = f" ({article.sentiment_score:.1f})" if article.sentiment_score is not None else ""
            sentiment_display = f"\n[bold {sentiment_color}]{article.sentiment.upper()}{score}[/bold {sentiment_color}]"
        
        self.console.print(
            Panel(
                f"[cyan]{article.summarized_headline or article.title}[/cyan]{sentiment_display}\n"
                f"[dim]{article.source} • {article.published_at}[/dim]\n"
                f"[link={article.url}]{article.url}[/link]\n\n"
                + "\n".join(f"[white]• {bullet}[/white]" for bullet in article.summary_bullets)
                + f"\n\n[magenta]Why it matters: {article.why_it_matters}[/magenta]",
                expand=False,
            )
        )

    def output_to_console(self, articles: List[Article]) -> None:
        """Output articles to console."""
        self.console.print(f"[bold green]Financial News Briefing • {self.today}[/bold green]\n")
        for article in articles:
            self._format_article_console(article)
            self.console.print("")

    def output_to_markdown(self, articles: List[Article]) -> str:
        """Output articles to markdown file."""
        filepath = self.briefings_dir / f"{self.today}.md"
        
        md_content = f"# Financial News Briefing • {self.today}\n\n"
        for article in articles:
            md_content += self._format_article_markdown(article)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        return str(filepath)

    async def output_to_email(self, articles: List[Article]) -> bool:
        """Output articles as email (if configured)."""
        if not all([EMAIL_TO, EMAIL_FROM, EMAIL_PASSWORD, EMAIL_SERVER]):
            logger.warning("Email configuration incomplete, skipping email delivery")
            return False

        try:
            # Setup email content
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Financial News Briefing • {self.today}"
            msg["From"] = EMAIL_FROM
            msg["To"] = EMAIL_TO

            # Create email body as plain text
            text_content = f"Financial News Briefing • {self.today}\n\n"
            for article in articles:
                text_content += f"{article.summarized_headline or article.title}\n"
                text_content += f"Source: {article.source}\n"
                for bullet in article.summary_bullets:
                    text_content += f"• {bullet}\n"
                text_content += f"\nWhy it matters: {article.why_it_matters}\n"
                text_content += f"{article.url}\n\n"

            # Create email body as HTML
            html_content = f"""
            <html>
            <head><style>
            body {{ font-family: Arial, sans-serif; }}
            h1 {{ color: #333366; }}
            h2 {{ color: #0066cc; margin-bottom: 5px; }}
            .source {{ color: #666; font-style: italic; margin-top: 0; }}
            .insight {{ color: #990066; font-weight: bold; }}
            </style></head>
            <body>
            <h1>Financial News Briefing • {self.today}</h1>
            """
            
            for article in articles:
                html_content += f"""
                <h2><a href="{article.url}">{article.summarized_headline or article.title}</a></h2>
                <p class="source">Source: {article.source} • {article.published_at}</p>
                <ul>
                """
                for bullet in article.summary_bullets:
                    html_content += f"<li>{bullet}</li>\n"
                    
                html_content += f"""
                </ul>
                <p class="insight">Why it matters: {article.why_it_matters}</p>
                <hr>
                """
                
            html_content += "</body></html>"
            
            # Attach parts
            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(EMAIL_SERVER, EMAIL_PORT) as server:
                server.starttls()
                server.login(EMAIL_FROM, EMAIL_PASSWORD)
                server.send_message(msg)
                
            logger.info(f"Email sent to {EMAIL_TO}")
            return True
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False


async def main(queries: List[str], max_articles: int = 20, model: str = "gpt-3.5-turbo"):
    """Main entry point for the news summarization pipeline."""
    start_time = time.time()
    
    # Input validation
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is required but not found in environment variables or .env file")
        sys.exit(1)
    
    if not NEWS_API_KEY:
        logger.error("NEWS_API_KEY is required but not found in environment variables or .env file")
        sys.exit(1)
    
    if not queries:
        logger.error("At least one query (ticker, keyword, or RSS URL) is required")
        sys.exit(1)
    
    # Initialize components
    async with aiohttp.ClientSession() as session:
        news_fetcher = NewsFetcher(session)
        news_summarizer = NewsSummarizer(model=model)
        news_outputter = NewsOutputter(console)
        
        # Fetch articles
        logger.info(f"Fetching news for queries: {', '.join(queries)}")
        articles = await news_fetcher.fetch_news(queries)
        
        # Limit to max_articles
        articles = articles[:max_articles]
        
        if not articles:
            logger.warning("No articles found for the provided queries")
            return
        
        logger.info(f"Found {len(articles)} articles to summarize")
        
        # Summarize articles
        summarized_articles = await news_summarizer.summarize_articles(articles)
        
        # Output results
        news_outputter.output_to_console(summarized_articles)
        md_path = news_outputter.output_to_markdown(summarized_articles)
        logger.info(f"Markdown briefing saved to {md_path}")
        
        # Send email if configured
        if EMAIL_TO:
            await news_outputter.output_to_email(summarized_articles)
        
        elapsed = time.time() - start_time
        logger.info(f"Process completed in {elapsed:.2f} seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Financial News Summarizer Agent")
    parser.add_argument(
        "--queries", "-q", 
        type=str, 
        nargs="+", 
        help="List of stock tickers, keywords, or RSS URLs to fetch news for"
    )
    parser.add_argument(
        "--config", "-c", 
        type=str, 
        help="Path to YAML config file with queries"
    )
    parser.add_argument(
        "--max", "-m", 
        type=int, 
        default=20, 
        help="Maximum number of articles to process"
    )
    parser.add_argument(
        "--model", 
        type=str, 
        default="gpt-3.5-turbo", 
        choices=["gpt-3.5-turbo", "gpt-4o"], 
        help="OpenAI model to use for summarization"
    )
    
    args = parser.parse_args()
    
    # Get queries from arguments or config file
    queries = []
    if args.queries:
        queries = args.queries
    elif args.config:
        try:
            import yaml
            with open(args.config, "r") as f:
                config = yaml.safe_load(f)
                queries = config.get("queries", [])
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)
    
    # Run the main async function
    asyncio.run(main(queries, args.max, args.model))


# TODO: Advanced Extensions
# - Vector-DB memory to track previously summarized articles
# - Sentiment scoring for articles and overall market mood
# - Automatic tagging and categorization of news topics
# - Portfolio-specific relevance scoring
# - Autonomous daily scheduling via cron job
# - Slack/Discord webhook integration
# - LangChain agent refactor for more complex reasoning
# - Retrieval-augmented generation for industry context
# - Custom fine-tuned financial summarization model
