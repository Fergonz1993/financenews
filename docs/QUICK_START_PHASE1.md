# Historical Document

This quick start describes an older streaming/agent exploration and is no longer the canonical implementation guide.

Use these docs instead:

- `README.md`
- `docs/product-north-star.md`
- `docs/architecture-current.md`

# 🚀 Quick Start: Phase 1 - Real-Time Financial News Streaming

## Prerequisites

You need Python 3.8+ and an OpenAI API key. Everything else can use demo/free tiers initially.

## Step-by-Step Setup

### 1. Install Dependencies
```bash
# Install new real-time dependencies
pip install websocket-client websockets python-socketio fastapi uvicorn rich
```

### 2. Test Environment Setup
```bash
# Quick environment check
python test_realtime_streams.py --env-check
```

### 3. Set API Keys (Optional but Recommended)
```bash
# In your .env file or environment
export OPENAI_API_KEY="your_openai_key_here"
export EODHD_API_KEY="your_eodhd_key"  # Optional: demo key works
export NEWSFILTER_API_KEY="your_newsfilter_key"  # Optional: for news stream
```

### 4. Run Real-Time Streaming Test
```bash
# Start the real-time streaming test
python test_realtime_streams.py
```

### 5. Run Full Real-Time Manager
```bash
# Start the complete real-time system
python realtime_websocket_manager.py
```

## What You'll See

### Immediate Results (Demo Mode):
- ✅ **Real-time crypto prices** from Binance (free)
- ✅ **Stock market data** from EODHD (demo symbols: AAPL, MSFT, TSLA)
- ✅ **Forex rates** (EURUSD, GBPUSD, USDJPY)
- ✅ **Live sentiment analysis** on incoming news
- ✅ **High-impact alerts** for major market movements

### Real-Time Dashboard:
```
╔══════════════════════════════════════════════════════════════════╗
║                Real-Time Streams Status                          ║
╠══════════════════════════════════════════════════════════════════╣
║ Stream          │ Status       │ Events    │ Last Event          ║
║ eodhd_trades    │ 🟢 Connected │ 1,247     │ 14:23:45           ║
║ binance_tickers │ 🟢 Connected │ 15,892    │ 14:23:46           ║
║ eodhd_forex     │ 🟢 Connected │ 432       │ 14:23:44           ║
╚══════════════════════════════════════════════════════════════════╝
```

### Live Event Stream:
```
📈 Trade: AAPL @ $185.2340 [eodhd]
📊 Ticker: BTCUSDT @ $43,567.89 [binance]
💱 Forex: EURUSD @ 1.08745 [eodhd]
📰 News: Apple reports Q4 earnings beat expectations... [newsfilter]
🧠 Sentiment: 📗 POSITIVE (0.85) for AAPL

🚨 HIGH IMPACT NEWS ALERT 🚨
Symbol: AAPL
Impact: POSITIVE (0.85)
Source: newsfilter
Time: 14:23:47
```

## Key Features Working Immediately

### 1. **Multi-Source Real-Time Data**
- **EODHD WebSocket**: Live US market data (<50ms latency)
- **Binance WebSocket**: Real-time crypto prices
- **NewsFilter.io**: Breaking financial news stream

### 2. **Event-Driven Processing**
- Automatic sentiment analysis on breaking news
- Real-time market impact scoring
- High-impact alert system

### 3. **Intelligent Analytics**
- AI-powered sentiment analysis using GPT-4o-mini
- Market correlation detection
- Price movement predictions

### 4. **Production-Ready Architecture**
- Async/await for high performance
- Automatic reconnection logic
- Error handling and logging
- Event queue processing

## Next Steps (Immediate Improvements)

### Add More Data Sources:
```bash
# Add Alpha Vantage for more news
export ALPHA_VANTAGE_API_KEY="your_key"

# Add Polygon for high-frequency data
export POLYGON_API_KEY="your_key"
```

### Enhance with Multi-Agent System:
```python
# Coming in Phase 2: Specialized AI agents
earnings_agent = EarningsAgent()
fed_agent = FedPolicyAgent()
crypto_agent = CryptoNewsAgent()
```

### Real-Time Dashboard Upgrade:
```bash
# Start web dashboard (Phase 3)
uvicorn dashboard:app --host 0.0.0.0 --port 8000
```

## Performance Metrics

### Expected Performance (Demo Mode):
- **Latency**: <500ms news-to-analysis
- **Throughput**: 1,000+ events/hour
- **Accuracy**: 85%+ sentiment classification
- **Uptime**: 95%+ WebSocket connections

### With Full API Keys:
- **Latency**: <100ms analysis
- **Throughput**: 10,000+ events/hour
- **Coverage**: 50,000+ global stocks
- **Real-time**: Sub-second market alerts

## Troubleshooting

### Common Issues:

**1. Import Errors:**
```bash
pip install -r enhanced_requirements_fixed.txt
```

**2. WebSocket Connection Failed:**
- Check internet connection
- Verify API keys
- Try demo mode first

**3. No Events Received:**
- Market hours: US 9:30 AM - 4:00 PM EST
- Crypto: 24/7
- News: Business hours typically

**4. High Memory Usage:**
- Normal for real-time processing
- Restart if >2GB usage

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Sources  │───▶│  WebSocket Mgr  │───▶│  Event Queue    │
│                 │    │                 │    │                 │
│ • EODHD        │    │ • Connections   │    │ • Async Proc   │
│ • Binance      │    │ • Parsers       │    │ • AI Analysis  │
│ • NewsFilter   │    │ • Auto-Reconnect│    │ • Alerts       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Dashboard     │◀───│  AI Analysis    │───▶│   Alerts        │
│                 │    │                 │    │                 │
│ • Live Tables   │    │ • Sentiment     │    │ • High Impact   │
│ • Event Stream  │    │ • Market Impact │    │ • Email/SMS     │
│ • Analytics     │    │ • Predictions   │    │ • Discord/Slack │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Ready for Phase 2?

Once Phase 1 is running smoothly, we'll implement:
- ✅ **Multi-Agent AI System** (5 specialized agents)
- ✅ **Advanced Analytics Dashboard** (React + WebSocket)
- ✅ **Predictive Models** (LSTM + Transformer + GNN ensemble)
- ✅ **Production Deployment** (Docker + Kubernetes)

**Let's get Phase 1 running first! 🚀**

Run: `python test_realtime_streams.py` to get started!
