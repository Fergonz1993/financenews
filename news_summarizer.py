#!/usr/bin/env python3
# news_summarizer.py - Financial News Summarizer Agent
# A production-ready CLI tool that fetches, summarizes and delivers financial news

import argparse
import asyncio
import json
import logging
import os
import re
import smtplib
import sys
import time
from datetime import datetime
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
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_SERVER = os.getenv("EMAIL_SERVER", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))

# Initialize OpenAI client
openai.api_key = OPENAI_API_KEY

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

    async def fetch_from_newsapi(
        self, query: str, page_size: int = 100
    ) -> List[Article]:
        """Fetch news articles from NewsAPI based on query."""
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

    async def fetch_news(self, queries: List[str]) -> List[Article]:
        """Fetch news from all sources based on queries."""
        all_articles: Set[Article] = set()
        for query in queries:
            articles = await self.fetch_from_newsapi(query)
            all_articles.update(articles)

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
Return JSON with keys: "headline", "summary_bullets", "why_it_matters"."""

                response = await openai.ChatCompletion.acreate(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                    max_tokens=300,
                )

                # Parse the response
                content = response.choices[0].message.content.strip()
                
                # Handle different response formats
                try:
                    # Try to parse as JSON
                    summary_data = json.loads(content)
                    article.summarized_headline = summary_data.get("headline", "")
                    article.summary_bullets = summary_data.get("summary_bullets", [])
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
        md = f"## [{article.summarized_headline or article.title}]({article.url})\n"
        md += f"*Source: {article.source}*\n\n"
        for bullet in article.summary_bullets:
            md += f"* {bullet}\n"
        md += f"\n**Why it matters:** {article.why_it_matters}\n\n"
        md += f"*Published: {article.published_at}*\n\n---\n\n"
        return md

    def _format_article_console(self, article: Article) -> None:
        """Format an article for console output with colors."""
        self.console.print(
            Panel(
                f"[cyan]{article.summarized_headline or article.title}[/cyan]\n"
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
