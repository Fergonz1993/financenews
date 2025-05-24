#!/usr/bin/env python3
"""
Real-Time WebSocket Manager for Financial News and Market Data
Implements live streaming from multiple financial data sources with event-driven processing.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
import websocket
import threading

import aiohttp
import websockets
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel

# Import our existing modules
from enhanced_news_summarizer import Article, EnhancedNewsSummarizer, Config

logger = logging.getLogger(__name__)
console = Console()

@dataclass
class StreamConfig:
    """Configuration for WebSocket streams."""
    url: str
    api_key: Optional[str] = None
    subscribe_message: Optional[Dict] = None
    enabled: bool = True
    reconnect_interval: int = 5
    max_reconnects: int = 10

@dataclass
class StreamEvent:
    """Represents a real-time event from a data stream."""
    source: str
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime
    symbol: Optional[str] = None
    price: Optional[float] = None
    sentiment_score: Optional[float] = None

class RealTimeStreamManager:
    """Manages multiple WebSocket connections for real-time financial data."""
    
    def __init__(self, config: Config):
        self.config = config
        self.console = Console()
        
        # Event handlers
        self.event_handlers: Dict[str, List[Callable]] = {
            'news': [],
            'trade': [],
            'ticker': [],
            'sentiment': []
        }
        
        # Stream configurations
        self.streams = self._setup_stream_configs()
        
        # Active connections
        self.connections: Dict[str, websocket.WebSocketApp] = {}
        self.connection_status: Dict[str, bool] = {}
        
        # Event queue for processing
        self.event_queue = asyncio.Queue()
        
        # Statistics
        self.stats = {
            'events_processed': 0,
            'connections_active': 0,
            'last_event_time': None,
            'start_time': datetime.now()
        }
        
        # News summarizer for real-time analysis
        self.news_summarizer = None
        
    def _setup_stream_configs(self) -> Dict[str, StreamConfig]:
        """Setup WebSocket stream configurations."""
        
        # Get API keys from environment
        eodhd_key = os.getenv('EODHD_API_KEY', 'demo')
        newsfilter_key = os.getenv('NEWSFILTER_API_KEY')
        
        return {
            'eodhd_trades': StreamConfig(
                url=f'wss://ws.eodhistoricaldata.com/ws/us?api_token={eodhd_key}',
                subscribe_message={
                    "action": "subscribe",
                    "symbols": "AAPL,MSFT,GOOGL,AMZN,TSLA,NVDA,META"
                }
            ),
            
            'eodhd_forex': StreamConfig(
                url=f'wss://ws.eodhistoricaldata.com/ws/forex?api_token={eodhd_key}',
                subscribe_message={
                    "action": "subscribe", 
                    "symbols": "EURUSD,GBPUSD,USDJPY"
                }
            ),
            
            'binance_tickers': StreamConfig(
                url='wss://stream.binance.com:9443/ws/!ticker@arr',
                subscribe_message=None  # Auto-subscribes to all tickers
            ),
            
            'newsfilter': StreamConfig(
                url='wss://api.newsfilter.io/stream',
                api_key=newsfilter_key,
                subscribe_message={
                    "type": "subscribe",
                    "channels": ["financial", "earnings", "fed"]
                } if newsfilter_key else None,
                enabled=bool(newsfilter_key)
            )
        }
    
    def add_event_handler(self, event_type: str, handler: Callable):
        """Add an event handler for specific event types."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    async def emit_event(self, event: StreamEvent):
        """Emit an event to all registered handlers."""
        await self.event_queue.put(event)
        
        # Call synchronous handlers
        for handler in self.event_handlers.get(event.event_type, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")
    
    def _create_websocket_handler(self, stream_name: str, stream_config: StreamConfig):
        """Create WebSocket event handlers for a specific stream."""
        
        def on_open(ws):
            logger.info(f"✅ Connected to {stream_name}")
            self.connection_status[stream_name] = True
            self.stats['connections_active'] += 1
            
            # Send subscribe message if configured
            if stream_config.subscribe_message:
                ws.send(json.dumps(stream_config.subscribe_message))
                logger.info(f"📡 Subscribed to {stream_name}")
        
        def on_message(ws, message):
            try:
                data = json.loads(message)
                event = self._parse_message(stream_name, data)
                if event:
                    # Use asyncio to handle the event
                    asyncio.create_task(self.emit_event(event))
                    self.stats['events_processed'] += 1
                    self.stats['last_event_time'] = datetime.now()
                    
            except Exception as e:
                logger.error(f"Error processing message from {stream_name}: {e}")
        
        def on_error(ws, error):
            logger.error(f"❌ WebSocket error for {stream_name}: {error}")
            self.connection_status[stream_name] = False
        
        def on_close(ws, close_status_code, close_msg):
            logger.warning(f"🔌 Connection closed for {stream_name}")
            self.connection_status[stream_name] = False
            self.stats['connections_active'] = max(0, self.stats['connections_active'] - 1)
            
            # Auto-reconnect
            if stream_config.enabled:
                threading.Timer(stream_config.reconnect_interval, 
                              lambda: self._reconnect_stream(stream_name)).start()
        
        return on_open, on_message, on_error, on_close
    
    def _parse_message(self, stream_name: str, data: Dict) -> Optional[StreamEvent]:
        """Parse incoming WebSocket message into a StreamEvent."""
        
        try:
            if stream_name.startswith('eodhd'):
                return self._parse_eodhd_message(stream_name, data)
            elif stream_name == 'binance_tickers':
                return self._parse_binance_message(data)
            elif stream_name == 'newsfilter':
                return self._parse_news_message(data)
            
        except Exception as e:
            logger.error(f"Error parsing message from {stream_name}: {e}")
        
        return None
    
    def _parse_eodhd_message(self, stream_name: str, data: Dict) -> Optional[StreamEvent]:
        """Parse EODHD WebSocket message."""
        
        if 'trades' in stream_name:
            return StreamEvent(
                source='eodhd',
                event_type='trade',
                data=data,
                timestamp=datetime.now(),
                symbol=data.get('s'),
                price=float(data.get('p', 0))
            )
        elif 'forex' in stream_name:
            return StreamEvent(
                source='eodhd',
                event_type='forex',
                data=data,
                timestamp=datetime.now(),
                symbol=data.get('s'),
                price=float(data.get('a', 0))  # Ask price
            )
        
        return None
    
    def _parse_binance_message(self, data: Dict) -> Optional[StreamEvent]:
        """Parse Binance WebSocket message."""
        
        # Handle array of ticker data
        if isinstance(data, list) and len(data) > 0:
            # Process first ticker for now
            ticker = data[0]
            return StreamEvent(
                source='binance',
                event_type='ticker',
                data=ticker,
                timestamp=datetime.now(),
                symbol=ticker.get('s'),
                price=float(ticker.get('c', 0))  # Close price
            )
        
        return None
    
    def _parse_news_message(self, data: Dict) -> Optional[StreamEvent]:
        """Parse news WebSocket message."""
        
        if data.get('type') == 'article':
            return StreamEvent(
                source='newsfilter',
                event_type='news',
                data=data,
                timestamp=datetime.now(),
                symbol=data.get('symbols', [None])[0] if data.get('symbols') else None
            )
        
        return None
    
    def _reconnect_stream(self, stream_name: str):
        """Reconnect to a WebSocket stream."""
        if stream_name in self.streams and self.streams[stream_name].enabled:
            logger.info(f"🔄 Reconnecting to {stream_name}")
            self.start_stream(stream_name)
    
    def start_stream(self, stream_name: str):
        """Start a specific WebSocket stream."""
        
        if stream_name not in self.streams:
            logger.error(f"Unknown stream: {stream_name}")
            return
        
        stream_config = self.streams[stream_name]
        if not stream_config.enabled:
            logger.info(f"Stream {stream_name} is disabled")
            return
        
        # Create WebSocket handlers
        on_open, on_message, on_error, on_close = self._create_websocket_handler(
            stream_name, stream_config
        )
        
        # Create WebSocket connection
        ws = websocket.WebSocketApp(
            stream_config.url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        
        self.connections[stream_name] = ws
        
        # Start connection in a separate thread
        def run_websocket():
            try:
                ws.run_forever()
            except Exception as e:
                logger.error(f"WebSocket error for {stream_name}: {e}")
        
        thread = threading.Thread(target=run_websocket, daemon=True)
        thread.start()
        
        logger.info(f"🚀 Started stream: {stream_name}")
    
    def start_all_streams(self):
        """Start all enabled WebSocket streams."""
        logger.info("🌐 Starting all WebSocket streams...")
        
        for stream_name, stream_config in self.streams.items():
            if stream_config.enabled:
                self.start_stream(stream_name)
                time.sleep(1)  # Stagger connections
        
        console.print("[green]✅ All streams started![/green]")
    
    def stop_all_streams(self):
        """Stop all WebSocket streams."""
        logger.info("🛑 Stopping all streams...")
        
        for stream_name, ws in self.connections.items():
            try:
                ws.close()
                self.connection_status[stream_name] = False
            except:
                pass
        
        self.connections.clear()
        self.stats['connections_active'] = 0
        console.print("[red]🛑 All streams stopped![/red]")
    
    async def process_event_queue(self):
        """Process events from the queue."""
        while True:
            try:
                event = await self.event_queue.get()
                await self._process_event(event)
                self.event_queue.task_done()
            except Exception as e:
                logger.error(f"Error processing event: {e}")
    
    async def _process_event(self, event: StreamEvent):
        """Process a single event."""
        
        # Real-time news analysis
        if event.event_type == 'news':
            await self._process_news_event(event)
        
        # Market data analysis
        elif event.event_type in ['trade', 'ticker', 'forex']:
            await self._process_market_event(event)
    
    async def _process_news_event(self, event: StreamEvent):
        """Process real-time news events."""
        
        try:
            # Create Article object
            article_data = event.data
            article = Article(
                title=article_data.get('title', ''),
                url=article_data.get('url', ''),
                source=event.source,
                published_at=article_data.get('publishedAt', event.timestamp.isoformat()),
                content=article_data.get('description', '')
            )
            
            # Real-time sentiment analysis
            if self.news_summarizer:
                analyzed_article = await self.news_summarizer.summarize_article(article)
                
                # Emit processed article event
                processed_event = StreamEvent(
                    source=event.source,
                    event_type='sentiment',
                    data=analyzed_article.to_dict(),
                    timestamp=event.timestamp,
                    symbol=event.symbol,
                    sentiment_score=analyzed_article.sentiment_score
                )
                
                await self.emit_event(processed_event)
            
        except Exception as e:
            logger.error(f"Error processing news event: {e}")
    
    async def _process_market_event(self, event: StreamEvent):
        """Process real-time market data events."""
        
        # Store market data for correlation analysis
        # This could be extended to detect price movements
        # correlating with news sentiment
        pass
    
    def get_status_table(self) -> Table:
        """Create a status table for the dashboard."""
        
        table = Table(title="Real-Time Streams Status")
        table.add_column("Stream", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Events", style="yellow")
        table.add_column("Last Event", style="blue")
        
        for stream_name, config in self.streams.items():
            if not config.enabled:
                continue
                
            status = "🟢 Connected" if self.connection_status.get(stream_name) else "🔴 Disconnected"
            
            table.add_row(
                stream_name,
                status,
                str(self.stats['events_processed']),
                str(self.stats['last_event_time'].strftime('%H:%M:%S') if self.stats['last_event_time'] else 'None')
            )
        
        return table
    
    async def start_dashboard(self):
        """Start real-time dashboard."""
        
        with Live(console=console, refresh_per_second=2) as live:
            while True:
                # Update status table
                status_table = self.get_status_table()
                
                # Create dashboard layout
                dashboard = Panel(
                    status_table,
                    title="[bold green]Financial News Real-Time Monitor[/bold green]",
                    subtitle=f"Running for {datetime.now() - self.stats['start_time']}"
                )
                
                live.update(dashboard)
                await asyncio.sleep(0.5)

# Example usage and event handlers
class NewsAlertSystem:
    """Example alert system for high-impact news."""
    
    def __init__(self):
        self.high_impact_threshold = 0.8
    
    async def handle_sentiment_event(self, event: StreamEvent):
        """Handle sentiment analysis events."""
        
        sentiment_score = event.sentiment_score or 0
        
        if abs(sentiment_score) > self.high_impact_threshold:
            impact_type = "POSITIVE" if sentiment_score > 0 else "NEGATIVE"
            
            console.print(f"""
[bold red]🚨 HIGH IMPACT NEWS ALERT 🚨[/bold red]
Symbol: {event.symbol or 'MARKET'}
Impact: {impact_type} ({sentiment_score:.2f})
Source: {event.source}
Time: {event.timestamp.strftime('%H:%M:%S')}
""")

async def main():
    """Main function to run the real-time stream manager."""
    
    # Setup configuration
    config = Config()
    
    # Create stream manager
    stream_manager = RealTimeStreamManager(config)
    
    # Setup news summarizer for real-time analysis
    from enhanced_news_summarizer import CacheManager
    cache = CacheManager()
    stream_manager.news_summarizer = EnhancedNewsSummarizer(config, cache)
    
    # Setup alert system
    alert_system = NewsAlertSystem()
    stream_manager.add_event_handler('sentiment', alert_system.handle_sentiment_event)
    
    # Start event processing
    asyncio.create_task(stream_manager.process_event_queue())
    
    # Start all streams
    stream_manager.start_all_streams()
    
    # Start dashboard
    try:
        await stream_manager.start_dashboard()
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
        stream_manager.stop_all_streams()

if __name__ == "__main__":
    asyncio.run(main()) 