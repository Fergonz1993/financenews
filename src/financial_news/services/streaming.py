#!/usr/bin/env python3
"""
Real-Time Financial News Streaming Analyzer
Advanced WebSocket-based system for instantaneous financial news processing.
"""

import asyncio
import contextlib
import hashlib
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

import aiohttp
import redis.asyncio as redis
import websockets

# Advanced event processing
from asyncio_throttle import Throttler
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)
console = Console()


class EventPriority(Enum):
    """Event priority levels for processing queue."""

    CRITICAL = 1  # Market-moving events
    HIGH = 2  # Company-specific major news
    MEDIUM = 3  # Sector updates
    LOW = 4  # General market commentary


class NewsEventType(Enum):
    """Types of financial news events."""

    EARNINGS = "earnings"
    ACQUISITION = "acquisition"
    REGULATORY = "regulatory"
    ECONOMIC_DATA = "economic_data"
    ANALYST_UPGRADE = "analyst_upgrade"
    ANALYST_DOWNGRADE = "analyst_downgrade"
    DIVIDEND = "dividend"
    INSIDER_TRADING = "insider_trading"
    BANKRUPTCY = "bankruptcy"
    IPO = "ipo"
    GENERAL = "general"


@dataclass
class StreamingNewsEvent:
    """Real-time news event structure."""

    id: str
    timestamp: datetime
    source: str
    title: str
    content: str
    entities: list[str]
    event_type: NewsEventType
    priority: EventPriority
    sentiment_score: float | None = None
    market_impact_score: float | None = None
    confidence: float | None = None
    tickers: list[str] = None

    def __post_init__(self):
        if self.tickers is None:
            self.tickers = []

    def to_dict(self) -> dict:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["event_type"] = self.event_type.value
        data["priority"] = self.priority.value
        return data


class EventBuffer:
    """Advanced circular buffer for real-time event management."""

    def __init__(self, max_size: int = 10000, time_window_minutes: int = 60):
        self.max_size = max_size
        self.time_window = timedelta(minutes=time_window_minutes)
        self.events: deque = deque(maxlen=max_size)
        self.event_index: dict[str, StreamingNewsEvent] = {}
        self.ticker_index: dict[str, set[str]] = defaultdict(set)
        self.priority_queues: dict[EventPriority, deque] = {
            priority: deque() for priority in EventPriority
        }

    def add_event(self, event: StreamingNewsEvent):
        """Add event to buffer with indexing."""

        # Remove old events outside time window
        self._cleanup_old_events()

        # Add to main buffer
        if len(self.events) >= self.max_size:
            old_event = self.events.popleft()
            self._remove_from_indexes(old_event)

        self.events.append(event)
        self.event_index[event.id] = event

        # Update ticker index
        for ticker in event.tickers:
            self.ticker_index[ticker].add(event.id)

        # Add to priority queue
        self.priority_queues[event.priority].append(event.id)

    def get_events_by_ticker(
        self, ticker: str, limit: int = 50
    ) -> list[StreamingNewsEvent]:
        """Get recent events for a specific ticker."""
        event_ids = list(self.ticker_index.get(ticker, set()))[-limit:]
        return [self.event_index[eid] for eid in event_ids if eid in self.event_index]

    def get_priority_events(
        self, priority: EventPriority, limit: int = 20
    ) -> list[StreamingNewsEvent]:
        """Get events by priority level."""
        queue = self.priority_queues[priority]
        event_ids = list(queue)[-limit:]
        return [self.event_index[eid] for eid in event_ids if eid in self.event_index]

    def _cleanup_old_events(self):
        """Remove events outside time window."""
        cutoff_time = datetime.now() - self.time_window

        while self.events and self.events[0].timestamp < cutoff_time:
            old_event = self.events.popleft()
            self._remove_from_indexes(old_event)

    def _remove_from_indexes(self, event: StreamingNewsEvent):
        """Remove event from all indexes."""
        self.event_index.pop(event.id, None)

        for ticker in event.tickers:
            self.ticker_index[ticker].discard(event.id)

        # Remove from priority queues
        for queue in self.priority_queues.values():
            with contextlib.suppress(ValueError):
                queue.remove(event.id)


class StreamingNewsClassifier:
    """Advanced real-time news classification."""

    def __init__(self):
        # Market-moving keywords by category
        self.critical_patterns = {
            "earnings": [
                "earnings",
                "quarterly results",
                "eps",
                "revenue beat",
                "revenue miss",
            ],
            "acquisitions": ["acquisition", "merger", "buyout", "takeover", "deal"],
            "regulatory": [
                "fda approval",
                "regulatory approval",
                "investigation",
                "lawsuit",
            ],
            "economic": ["fed", "interest rate", "inflation", "gdp", "unemployment"],
        }

        self.sentiment_patterns = {
            "very_positive": [
                "soars",
                "surges",
                "beats estimates",
                "record high",
                "breakthrough",
            ],
            "positive": ["rises", "gains", "up", "positive", "strong"],
            "negative": ["falls", "drops", "misses", "disappoints", "weak"],
            "very_negative": [
                "plummets",
                "crashes",
                "collapses",
                "investigation",
                "bankruptcy",
            ],
        }

    def classify_event(
        self, title: str, content: str, source: str
    ) -> tuple[NewsEventType, EventPriority]:
        """Classify news event type and priority."""

        text = f"{title} {content}".lower()

        # Determine event type
        event_type = self._determine_event_type(text)

        # Determine priority
        priority = self._determine_priority(text, event_type, source)

        return event_type, priority

    def extract_sentiment(self, title: str, content: str) -> tuple[float, float]:
        """Extract sentiment score and confidence."""

        text = f"{title} {content}".lower()
        sentiment_score = 0.0
        confidence = 0.0

        # Count sentiment patterns
        sentiment_counts = {
            "very_positive": 0,
            "positive": 0,
            "negative": 0,
            "very_negative": 0,
        }

        for sentiment_type, patterns in self.sentiment_patterns.items():
            for pattern in patterns:
                if pattern in text:
                    sentiment_counts[sentiment_type] += text.count(pattern)

        # Calculate weighted sentiment score
        total_signals = sum(sentiment_counts.values())
        if total_signals > 0:
            score = (
                sentiment_counts["very_positive"] * 1.0
                + sentiment_counts["positive"] * 0.5
                + sentiment_counts["negative"] * -0.5
                + sentiment_counts["very_negative"] * -1.0
            ) / total_signals

            sentiment_score = max(-1.0, min(1.0, score))
            confidence = min(1.0, total_signals / 10.0)  # Max confidence at 10+ signals

        return sentiment_score, confidence

    def extract_tickers(self, title: str, content: str) -> list[str]:
        """Extract stock tickers from text."""
        import re

        text = f"{title} {content}"

        # Pattern for stock tickers (1-5 uppercase letters)
        ticker_pattern = r"\b([A-Z]{1,5})\b"

        # Common false positives to filter out
        false_positives = {
            "THE",
            "AND",
            "FOR",
            "ARE",
            "BUT",
            "NOT",
            "YOU",
            "ALL",
            "CAN",
            "HER",
            "WAS",
            "ONE",
            "OUR",
            "HAD",
            "BY",
            "WHO",
            "FROM",
            "THIS",
            "NEW",
            "NOW",
            "OLD",
            "SEE",
            "TWO",
            "WAY",
            "ITS",
            "DID",
            "GET",
            "MAY",
            "HIM",
            "HIS",
            "HAS",
            "OFF",
            "SET",
            "TOP",
            "PUT",
            "END",
            "WHY",
            "TRY",
            "GOT",
            "RUN",
            "HOT",
            "CUT",
            "LET",
            "YES",
            "YET",
            "SHE",
            "USE",
            "OWN",
            "SAY",
            "HOW",
            "MAN",
            "BOY",
            "BIG",
            "BAD",
            "FEW",
            "DAY",
            "LOT",
            "WAR",
            "FAR",
            "AGO",
            "WON",
            "ANY",
            "SUN",
            "SON",
            "ART",
            "ACT",
            "AGE",
            "EYE",
            "ARM",
            "EAR",
            "EGG",
            "AID",
            "ICE",
            "OIL",
            "AIR",
            "BAG",
            "BAR",
            "BAT",
            "BED",
            "BEE",
            "BIT",
            "BOX",
            "BUS",
            "BUG",
            "CAR",
            "CAT",
            "COW",
            "CUP",
            "DOG",
            "ELF",
            "FAN",
            "FIG",
            "FOX",
            "GAS",
            "GUN",
            "HAT",
            "HEN",
            "JAR",
            "JOB",
            "KEY",
            "KID",
            "LAW",
            "LEG",
            "LID",
            "LOG",
            "MOM",
            "NET",
            "NUT",
            "PAN",
            "PEN",
            "PET",
            "PIE",
            "PIG",
            "POT",
            "RAT",
            "RED",
            "SIR",
            "SIX",
            "SKY",
            "TAX",
            "TEN",
            "TIE",
            "TIP",
            "TOY",
            "VAN",
            "WEB",
            "WIN",
            "ZIP",
        }

        tickers = []
        matches = re.findall(ticker_pattern, text)

        for match in matches:
            if match not in false_positives and len(match) <= 5:
                tickers.append(match)

        return list(set(tickers))  # Remove duplicates

    def _determine_event_type(self, text: str) -> NewsEventType:
        """Determine the type of news event."""

        for event_type, patterns in self.critical_patterns.items():
            for pattern in patterns:
                if pattern in text:
                    return NewsEventType(event_type)

        # Default to general if no specific pattern found
        return NewsEventType.GENERAL

    def _determine_priority(
        self, text: str, event_type: NewsEventType, source: str
    ) -> EventPriority:
        """Determine event priority based on content and source."""

        # Critical events
        critical_keywords = ["breaking", "urgent", "halt", "suspended", "emergency"]
        if any(keyword in text for keyword in critical_keywords):
            return EventPriority.CRITICAL

        # High priority sources
        high_priority_sources = [
            "reuters",
            "bloomberg",
            "cnbc",
            "sec",
            "federal reserve",
        ]
        if any(source_name in source.lower() for source_name in high_priority_sources):
            if event_type in [
                NewsEventType.EARNINGS,
                NewsEventType.ACQUISITION,
                NewsEventType.REGULATORY,
            ]:
                return EventPriority.HIGH

        # Medium priority for sector updates
        if event_type in [
            NewsEventType.ANALYST_UPGRADE,
            NewsEventType.ANALYST_DOWNGRADE,
        ]:
            return EventPriority.MEDIUM

        return EventPriority.LOW


class RealTimeNewsStream:
    """Advanced real-time news streaming manager."""

    def __init__(self, max_concurrent_connections: int = 10):
        self.event_buffer = EventBuffer()
        self.classifier = StreamingNewsClassifier()
        self.subscribers: dict[str, Callable] = {}
        self.is_running = False
        self.max_concurrent = max_concurrent_connections
        self.throttler = Throttler(rate_limit=100, period=1)  # 100 requests per second

        # Redis for distributed caching
        self.redis_client: redis.Redis | None = None

        # Performance metrics
        self.metrics = {
            "events_processed": 0,
            "events_per_second": 0,
            "last_event_time": None,
            "error_count": 0,
            "connection_count": 0,
        }

        # WebSocket connections
        self.websocket_connections: set[websockets.WebSocketServerProtocol] = set()

    async def initialize(self, redis_url: str = "redis://localhost:6379"):
        """Initialize streaming components."""

        try:
            self.redis_client = await redis.from_url(redis_url)
            await self.redis_client.ping()
            logger.info("✅ Redis connection established")
        except Exception as e:
            logger.warning(f"⚠️  Redis connection failed: {e}")

        logger.info("🚀 Real-time streaming analyzer initialized")

    async def start_websocket_server(self, host: str = "localhost", port: int = 8765):
        """Start WebSocket server for real-time event broadcasting."""

        async def handle_websocket(websocket, path):
            """Handle individual WebSocket connections."""

            self.websocket_connections.add(websocket)
            self.metrics["connection_count"] = len(self.websocket_connections)

            try:
                logger.info(f"📡 New WebSocket connection: {websocket.remote_address}")

                # Send initial data
                await self._send_initial_data(websocket)

                # Keep connection alive and handle incoming messages
                async for message in websocket:
                    await self._handle_websocket_message(websocket, message)

            except websockets.exceptions.ConnectionClosed:
                logger.info(
                    f"🔌 WebSocket connection closed: {websocket.remote_address}"
                )
            except Exception as e:
                logger.error(f"❌ WebSocket error: {e}")
            finally:
                self.websocket_connections.discard(websocket)
                self.metrics["connection_count"] = len(self.websocket_connections)

        logger.info(f"🌐 Starting WebSocket server on {host}:{port}")

        async with websockets.serve(handle_websocket, host, port):
            self.is_running = True
            logger.info("✅ WebSocket server started successfully")

            # Keep server running
            try:
                await asyncio.Future()  # Run forever
            except asyncio.CancelledError:
                logger.info("🛑 WebSocket server shutting down")
                self.is_running = False

    async def _send_initial_data(self, websocket):
        """Send initial data to new WebSocket connections."""

        # Send recent high-priority events
        recent_events = self.event_buffer.get_priority_events(
            EventPriority.CRITICAL, limit=10
        )
        recent_events.extend(
            self.event_buffer.get_priority_events(EventPriority.HIGH, limit=10)
        )

        initial_data = {
            "type": "initial_data",
            "events": [event.to_dict() for event in recent_events],
            "metrics": self.metrics.copy(),
            "timestamp": datetime.now().isoformat(),
        }

        await websocket.send(json.dumps(initial_data))

    async def _handle_websocket_message(self, websocket, message: str):
        """Handle incoming WebSocket messages."""

        try:
            data = json.loads(message)
            message_type = data.get("type")

            if message_type == "subscribe_ticker":
                ticker = data.get("ticker", "").upper()
                if ticker:
                    events = self.event_buffer.get_events_by_ticker(ticker, limit=20)
                    response = {
                        "type": "ticker_events",
                        "ticker": ticker,
                        "events": [event.to_dict() for event in events],
                        "timestamp": datetime.now().isoformat(),
                    }
                    await websocket.send(json.dumps(response))

            elif message_type == "get_metrics":
                response = {
                    "type": "metrics",
                    "data": self.metrics.copy(),
                    "timestamp": datetime.now().isoformat(),
                }
                await websocket.send(json.dumps(response))

        except Exception as e:
            logger.error(f"❌ Error handling WebSocket message: {e}")

    async def process_news_feed(self, source_url: str, source_name: str):
        """Process real-time news feed from various sources."""

        session_timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=session_timeout) as session:
            while self.is_running:
                try:
                    async with self.throttler:
                        await self._fetch_and_process_news(
                            session, source_url, source_name
                        )

                    await asyncio.sleep(1)  # Brief pause between requests

                except Exception as e:
                    logger.error(f"❌ Error processing feed {source_name}: {e}")
                    self.metrics["error_count"] += 1
                    await asyncio.sleep(5)  # Longer pause on error

    async def _fetch_and_process_news(
        self, session: aiohttp.ClientSession, source_url: str, source_name: str
    ):
        """Fetch and process news from a specific source."""

        try:
            async with session.get(source_url) as response:
                if response.status == 200:
                    data = await response.json()
                    await self._process_news_data(data, source_name)
                else:
                    logger.warning(f"⚠️  HTTP {response.status} from {source_name}")

        except asyncio.TimeoutError:
            logger.warning(f"⏰ Timeout fetching from {source_name}")
        except Exception as e:
            logger.error(f"❌ Error fetching from {source_name}: {e}")

    async def _process_news_data(self, data: dict, source_name: str):
        """Process incoming news data."""

        # Parse news items based on source format
        articles = self._parse_news_data(data, source_name)

        for article in articles:
            await self._create_and_process_event(article, source_name)

    def _parse_news_data(self, data: dict, source_name: str) -> list[dict]:
        """Parse news data based on source format."""

        articles = []

        # Handle different source formats
        if source_name.lower() == "newsapi":
            articles = data.get("articles", [])
        elif source_name.lower() == "reuters":
            articles = data.get("news", [])
        elif source_name.lower() == "bloomberg":
            articles = data.get("stories", [])
        else:
            # Generic format
            articles = data.get("items", data.get("articles", []))

        return articles

    async def _create_and_process_event(self, article: dict, source_name: str):
        """Create and process a streaming news event."""

        title = article.get("title", "")
        content = article.get("description", article.get("content", ""))

        if not title or not content:
            return

        # Generate unique event ID
        event_id = hashlib.md5(f"{title}{content}{source_name}".encode()).hexdigest()

        # Check for duplicates
        if event_id in self.event_buffer.event_index:
            return

        # Classify event
        event_type, priority = self.classifier.classify_event(
            title, content, source_name
        )
        sentiment_score, confidence = self.classifier.extract_sentiment(title, content)
        tickers = self.classifier.extract_tickers(title, content)

        # Create event
        event = StreamingNewsEvent(
            id=event_id,
            timestamp=datetime.now(),
            source=source_name,
            title=title,
            content=content,
            entities=[],  # Will be populated by entity extraction
            event_type=event_type,
            priority=priority,
            sentiment_score=sentiment_score,
            confidence=confidence,
            tickers=tickers,
        )

        # Add to buffer
        self.event_buffer.add_event(event)

        # Update metrics
        self.metrics["events_processed"] += 1
        self.metrics["last_event_time"] = datetime.now()

        # Broadcast to WebSocket clients
        await self._broadcast_event(event)

        # Cache in Redis if available
        if self.redis_client:
            await self._cache_event(event)

        logger.info(f"📰 Processed {priority.name} event: {title[:50]}...")

    async def _broadcast_event(self, event: StreamingNewsEvent):
        """Broadcast event to all WebSocket connections."""

        if not self.websocket_connections:
            return

        message = {
            "type": "new_event",
            "event": event.to_dict(),
            "timestamp": datetime.now().isoformat(),
        }

        message_json = json.dumps(message)

        # Send to all connected clients
        disconnected = set()
        for websocket in self.websocket_connections.copy():
            try:
                await websocket.send(message_json)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(websocket)
            except Exception as e:
                logger.error(f"❌ Error broadcasting to WebSocket: {e}")
                disconnected.add(websocket)

        # Remove disconnected clients
        self.websocket_connections -= disconnected
        self.metrics["connection_count"] = len(self.websocket_connections)

    async def _cache_event(self, event: StreamingNewsEvent):
        """Cache event in Redis for persistence."""

        try:
            event_data = json.dumps(event.to_dict())
            cache_key = f"news_event:{event.id}"

            # Cache with 24-hour expiration
            await self.redis_client.setex(cache_key, 86400, event_data)

            # Add to ticker-specific sets
            for ticker in event.tickers:
                ticker_key = f"ticker_events:{ticker}"
                await self.redis_client.zadd(ticker_key, {event.id: time.time()})
                await self.redis_client.expire(ticker_key, 86400)

        except Exception as e:
            logger.warning(f"⚠️  Redis caching failed: {e}")

    async def get_live_dashboard_data(self) -> dict:
        """Get data for live dashboard display."""

        # Get recent events by priority
        critical_events = self.event_buffer.get_priority_events(
            EventPriority.CRITICAL, limit=5
        )
        high_events = self.event_buffer.get_priority_events(
            EventPriority.HIGH, limit=10
        )

        # Calculate events per second
        current_time = time.time()
        if hasattr(self, "_last_metrics_time"):
            time_diff = current_time - self._last_metrics_time
            if time_diff > 0:
                events_diff = self.metrics["events_processed"] - getattr(
                    self, "_last_events_count", 0
                )
                self.metrics["events_per_second"] = round(events_diff / time_diff, 2)

        self._last_metrics_time = current_time
        self._last_events_count = self.metrics["events_processed"]

        return {
            "critical_events": [event.to_dict() for event in critical_events],
            "high_priority_events": [event.to_dict() for event in high_events],
            "metrics": self.metrics.copy(),
            "buffer_size": len(self.event_buffer.events),
            "active_tickers": len(self.event_buffer.ticker_index),
            "timestamp": datetime.now().isoformat(),
        }


class LiveDashboard:
    """Real-time dashboard for monitoring news streams."""

    def __init__(self, stream_manager: RealTimeNewsStream):
        self.stream_manager = stream_manager
        self.console = console

    async def start_live_display(self):
        """Start live dashboard display."""

        def generate_dashboard():
            """Generate dashboard table."""

            # Get live data
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create a new task to get the data
                    asyncio.create_task(self.stream_manager.get_live_dashboard_data())
                    data = {}  # Fallback to empty data for now
                else:
                    data = asyncio.run(self.stream_manager.get_live_dashboard_data())
            except Exception:
                data = {
                    "metrics": {},
                    "critical_events": [],
                    "high_priority_events": [],
                }

            # Create metrics table
            metrics_table = Table(title="📊 Real-Time Metrics")
            metrics_table.add_column("Metric", style="cyan")
            metrics_table.add_column("Value", style="magenta")

            metrics = data.get("metrics", {})
            metrics_table.add_row(
                "Events Processed", str(metrics.get("events_processed", 0))
            )
            metrics_table.add_row(
                "Events/Second", str(metrics.get("events_per_second", 0))
            )
            metrics_table.add_row(
                "Active Connections", str(metrics.get("connection_count", 0))
            )
            metrics_table.add_row("Error Count", str(metrics.get("error_count", 0)))

            # Create events table
            events_table = Table(title="🔥 Critical Events")
            events_table.add_column("Time", style="green", width=12)
            events_table.add_column("Source", style="blue", width=15)
            events_table.add_column("Title", style="white", width=50)
            events_table.add_column("Sentiment", style="yellow", width=10)

            for event in data.get("critical_events", [])[:5]:
                timestamp = datetime.fromisoformat(event["timestamp"]).strftime(
                    "%H:%M:%S"
                )
                sentiment = f"{event.get('sentiment_score', 0):.2f}"
                events_table.add_row(
                    timestamp,
                    event.get("source", "Unknown")[:14],
                    event.get("title", "No title")[:49],
                    sentiment,
                )

            return Panel.fit(
                f"{metrics_table}\n\n{events_table}",
                title="🚀 Real-Time Financial News Stream",
                border_style="blue",
            )

        # Start live display
        with Live(generate_dashboard(), refresh_per_second=2) as live:
            try:
                while self.stream_manager.is_running:
                    live.update(generate_dashboard())
                    await asyncio.sleep(0.5)
            except KeyboardInterrupt:
                logger.info("🛑 Dashboard stopped by user")


# Main integration function
async def start_realtime_analysis(config: dict):
    """Start real-time financial news analysis."""

    stream_manager = RealTimeNewsStream()
    await stream_manager.initialize()

    # Start WebSocket server
    websocket_task = asyncio.create_task(
        stream_manager.start_websocket_server(
            host=config.get("websocket_host", "localhost"),
            port=config.get("websocket_port", 8765),
        )
    )

    # Start news feeds
    news_sources = config.get(
        "news_sources",
        [
            {
                "url": "https://newsapi.org/v2/everything?q=stocks&apiKey=YOUR_KEY",
                "name": "NewsAPI",
            },
            {
                "url": "https://api.marketaux.com/v1/news/all?api_token=YOUR_TOKEN",
                "name": "MarketAux",
            },
        ],
    )

    feed_tasks = []
    for source in news_sources:
        task = asyncio.create_task(
            stream_manager.process_news_feed(source["url"], source["name"])
        )
        feed_tasks.append(task)

    # Start live dashboard
    dashboard = LiveDashboard(stream_manager)
    dashboard_task = asyncio.create_task(dashboard.start_live_display())

    # Wait for all tasks
    try:
        await asyncio.gather(websocket_task, *feed_tasks, dashboard_task)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down real-time analysis")
        for task in [websocket_task, dashboard_task, *feed_tasks]:
            task.cancel()


if __name__ == "__main__":
    # Example configuration
    config = {
        "websocket_host": "localhost",
        "websocket_port": 8765,
        "news_sources": [
            {"url": "https://newsapi.org/v2/everything?q=stocks", "name": "NewsAPI"},
        ],
    }

    try:
        asyncio.run(start_realtime_analysis(config))
    except KeyboardInterrupt:
        print("\n🛑 Real-time analysis stopped")
