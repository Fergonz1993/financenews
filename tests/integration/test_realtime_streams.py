#!/usr/bin/env python3
"""
Test script for Real-Time Financial News Streaming
Quick validation of WebSocket connections and event processing.
"""

import asyncio
import os
import sys
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test if we can import our modules
try:
    from realtime_websocket_manager import RealTimeStreamManager, NewsAlertSystem
    from enhanced_news_summarizer import Config, CacheManager, EnhancedNewsSummarizer
    print("✅ All imports successful!")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Run: pip install -r enhanced_requirements_fixed.txt")
    sys.exit(1)

class TestEventHandler:
    """Test event handler to validate events are being received."""
    
    def __init__(self):
        self.events_received = {
            'trade': 0,
            'ticker': 0,
            'news': 0,
            'sentiment': 0,
            'forex': 0
        }
        self.start_time = datetime.now()
    
    async def handle_trade_event(self, event):
        """Handle trade events."""
        self.events_received['trade'] += 1
        print(f"📈 Trade: {event.symbol} @ ${event.price:.4f} [{event.source}]")
    
    async def handle_ticker_event(self, event):
        """Handle ticker events."""
        self.events_received['ticker'] += 1
        if self.events_received['ticker'] % 10 == 0:  # Print every 10th ticker
            print(f"📊 Ticker: {event.symbol} @ ${event.price:.4f} [{event.source}]")
    
    async def handle_news_event(self, event):
        """Handle news events."""
        self.events_received['news'] += 1
        title = event.data.get('title', 'No title')[:50]
        print(f"📰 News: {title}... [{event.source}]")
    
    async def handle_sentiment_event(self, event):
        """Handle sentiment analysis events."""
        self.events_received['sentiment'] += 1
        score = event.sentiment_score or 0
        sentiment = "📗 POSITIVE" if score > 0.1 else "📕 NEGATIVE" if score < -0.1 else "📔 NEUTRAL"
        print(f"🧠 Sentiment: {sentiment} ({score:.2f}) for {event.symbol or 'MARKET'}")
    
    async def handle_forex_event(self, event):
        """Handle forex events."""
        self.events_received['forex'] += 1
        print(f"💱 Forex: {event.symbol} @ {event.price:.5f} [{event.source}]")
    
    def print_stats(self):
        """Print event statistics."""
        runtime = datetime.now() - self.start_time
        total_events = sum(self.events_received.values())
        
        print(f"""
╔══════════════════════════════════════════════════════════════════╗
║                        📊 EVENT STATISTICS                       ║
╠══════════════════════════════════════════════════════════════════╣
║ Runtime: {str(runtime).split('.')[0]}                                       ║
║ Total Events: {total_events:,}                                            ║
║                                                                  ║
║ Event Breakdown:                                                 ║
║   📈 Trades: {self.events_received['trade']:,}                                    ║
║   📊 Tickers: {self.events_received['ticker']:,}                                   ║
║   📰 News: {self.events_received['news']:,}                                      ║
║   🧠 Sentiment: {self.events_received['sentiment']:,}                               ║
║   💱 Forex: {self.events_received['forex']:,}                                     ║
╚══════════════════════════════════════════════════════════════════╝
""")

async def test_basic_functionality():
    """Test basic WebSocket functionality."""
    
    print("🚀 Starting Financial News Real-Time Stream Test")
    print("=" * 60)
    
    # Create configuration
    config = Config()
    
    # Create test event handler
    test_handler = TestEventHandler()
    
    # Create stream manager
    stream_manager = RealTimeStreamManager(config)
    
    # Create cache and news summarizer
    cache = CacheManager()
    stream_manager.news_summarizer = EnhancedNewsSummarizer(config, cache)
    
    # Register event handlers
    stream_manager.add_event_handler('trade', test_handler.handle_trade_event)
    stream_manager.add_event_handler('ticker', test_handler.handle_ticker_event)
    stream_manager.add_event_handler('news', test_handler.handle_news_event)
    stream_manager.add_event_handler('sentiment', test_handler.handle_sentiment_event)
    stream_manager.add_event_handler('forex', test_handler.handle_forex_event)
    
    # Setup alert system
    alert_system = NewsAlertSystem()
    stream_manager.add_event_handler('sentiment', alert_system.handle_sentiment_event)
    
    # Start event processing
    asyncio.create_task(stream_manager.process_event_queue())
    
    # Start streams
    print("🌐 Starting WebSocket streams...")
    stream_manager.start_all_streams()
    
    # Print status every 30 seconds
    async def print_periodic_stats():
        while True:
            await asyncio.sleep(30)
            test_handler.print_stats()
            
            # Print stream status
            print("\n📡 Stream Status:")
            for stream_name, status in stream_manager.connection_status.items():
                status_icon = "🟢" if status else "🔴"
                print(f"   {status_icon} {stream_name}")
    
    # Start periodic stats
    asyncio.create_task(print_periodic_stats())
    
    print(f"""
🎯 Test Configuration:
   - Demo mode using EODHD demo key
   - Monitoring: AAPL, MSFT, GOOGL, AMZN, TSLA, NVDA, META
   - Forex: EURUSD, GBPUSD, USDJPY
   - Crypto: All Binance tickers
   - News: Requires NEWSFILTER_API_KEY environment variable

💡 Tips:
   - Set EODHD_API_KEY for full market access
   - Set NEWSFILTER_API_KEY for real-time news
   - Press Ctrl+C to stop

📊 Real-time data will appear below:
""")
    
    try:
        # Run for test duration or until interrupted
        await asyncio.sleep(300)  # Run for 5 minutes
        
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    
    finally:
        print("\n📊 Final Statistics:")
        test_handler.print_stats()
        
        print("🛑 Stopping all streams...")
        stream_manager.stop_all_streams()
        
        print("✅ Test completed!")

async def test_environment():
    """Test environment setup and API keys."""
    
    print("🔍 Testing Environment Setup")
    print("=" * 40)
    
    # Check API keys
    api_keys = {
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
        'EODHD_API_KEY': os.getenv('EODHD_API_KEY', 'demo'),
        'NEWSFILTER_API_KEY': os.getenv('NEWSFILTER_API_KEY'),
        'NEWS_API_KEY': os.getenv('NEWS_API_KEY'),
        'FINNHUB_API_KEY': os.getenv('FINNHUB_API_KEY'),
    }
    
    for key, value in api_keys.items():
        if value:
            masked_value = value[:8] + "..." if len(value) > 8 else "***"
            print(f"✅ {key}: {masked_value}")
        else:
            print(f"⚠️  {key}: Not set")
    
    print("\n📁 Configuration Files:")
    config_files = ['config.yaml', 'env_template']
    for file in config_files:
        if os.path.exists(file):
            print(f"✅ {file}: Found")
        else:
            print(f"⚠️  {file}: Not found")
    
    print("\n🐍 Python Dependencies:")
    required_packages = [
        'websocket', 'websockets', 'aiohttp', 'rich', 
        'openai', 'redis', 'pandas', 'numpy'
    ]
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}: Installed")
        except ImportError:
            print(f"❌ {package}: Missing")

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════╗
║          📈 Financial News Real-Time Streaming Test 📈           ║
║                                                                  ║
║  This test validates WebSocket connections and event processing  ║
╚══════════════════════════════════════════════════════════════════╝
""")
    
    import argparse
    parser = argparse.ArgumentParser(description='Test real-time financial news streaming')
    parser.add_argument('--env-check', action='store_true', help='Check environment setup only')
    args = parser.parse_args()
    
    if args.env_check:
        asyncio.run(test_environment())
    else:
        asyncio.run(test_basic_functionality()) 