# Financial News — Real-Time Aggregation & Analysis Platform

[![CI](https://github.com/Fergonz1993/financenews/actions/workflows/ci.yml/badge.svg)](https://github.com/Fergonz1993/financenews/actions)
[![Next.js](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An open-source financial news platform that continuously aggregates articles from **18+ RSS feeds**, **GDELT**, **SEC EDGAR**, and **Newsdata.io** — with built-in sentiment analysis, entity extraction, and a live dashboard.

![Dashboard](https://img.shields.io/badge/status-active-brightgreen)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Continuous Ingestion** | Background loop fetches from all sources every 5 minutes |
| **18+ RSS Feeds** | Reuters, CNBC, Yahoo Finance, MarketWatch, WSJ, Bloomberg, FT, and more |
| **GDELT Connector** | Free global news via GDELT v2 DOC API (no API key) |
| **SEC EDGAR Connector** | SEC filings and press releases (no API key) |
| **Newsdata.io Connector** | Optional structured news API (free tier, 200 req/day) |
| **Sentiment Analysis** | VADER-based sentiment scoring on every article |
| **Entity Extraction** | Automatic company/person recognition |
| **Topic Modeling** | Finance, Markets, AI, Earnings, Policy classification |
| **Live Dashboard** | Next.js frontend with auto-refresh and filtering |
| **Admin Ingest Panel** | Real-time connector status, manual trigger, error log |
| **REST API** | Full CRUD for articles, sources, analytics, and ingestion |
| **WebSocket Notifications** | Real-time alerts for market events |
| **Cross-Source Dedup** | URL canonicalization + fuzzy title matching |

## 🏗 Architecture

```
┌─────────────────────────────────────────────────┐
│                  Next.js Frontend                │
│  Dashboard · Articles · Analytics · Admin Panel  │
│              (pages/ + components/)               │
└──────────────────────┬──────────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼──────────────────────────┐
│                  FastAPI Backend                  │
│         src/financial_news/api/main.py           │
├──────────────────────────────────────────────────┤
│  Continuous Runner        │  RSS Feed Ingestor   │
│  (GDELT · SEC · Newsdata) │  (18+ feeds)         │
├──────────────────────────────────────────────────┤
│  Sentiment Analysis · Entity Extraction · Topics │
├──────────────────────────────────────────────────┤
│                   PostgreSQL                     │
└──────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 16+ (or Docker)

### 1. Clone & Configure

```bash
git clone https://github.com/Fergonz1993/financenews.git
cd financenews
cp .env.example .env
# Edit .env — at minimum set your DB credentials
```

### 2. Backend Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Frontend Setup

```bash
npm install
```

### 4. Database

```bash
# Option A: Local PostgreSQL
createdb financenews

# Option B: Docker
docker compose up postgres -d
```

### 5. Run

```bash
python run_server.py
```

This starts both:

- **FastAPI** at `http://localhost:8000` (API + continuous ingestion)
- **Next.js** at `http://localhost:3000` (dashboard)

### Or use Docker

```bash
docker compose up --build
```

## 📡 Data Sources

### Free (No API Key)

| Source | Type | Articles/Cycle |
|--------|------|----------------|
| Reuters, CNBC, BBC, Yahoo Finance, MarketWatch | RSS | ~25 each |
| WSJ, Financial Times, The Economist, Nasdaq | RSS | ~25 each |
| Bloomberg (via Google News) | RSS | ~25 |
| Google News (Finance, Markets, AI, Earnings) | RSS | ~25 each |
| SEC Press Releases | RSS/Atom | ~25 |
| GDELT Project | REST API | ~25 |
| SEC EDGAR (full-text search) | REST API | ~25 |

### Optional (Free Tier, Needs Key)

| Source | Type | Limit |
|--------|------|-------|
| Newsdata.io | REST API | 200 req/day |

Set `NEWSDATA_API_KEY` in `.env` to enable.

## 🔌 API

### Articles

```
GET  /api/articles              # List with filters, pagination, sorting
GET  /api/articles/count        # Count matching filters
GET  /api/articles/{id}         # Single article detail
```

### Analytics

```
GET  /api/analytics             # Sentiment distribution, top entities/topics
```

### Sources

```
GET  /api/sources               # List configured sources
POST /api/sources               # Add/update a source
```

### Ingestion

```
POST /api/ingest                    # Run RSS ingestion now
POST /api/ingest/continuous/trigger # Run full cycle (all connectors + RSS)
GET  /api/ingest/status             # Status with connector health
GET  /api/ingest/continuous/status  # Detailed connector-level status
```

## 🧪 Tests

```bash
# Python unit tests (57 tests)
PYTHONPATH=src pytest tests/unit -v

# TypeScript type check
npx tsc --noEmit
```

## 📁 Project Structure

```
financenews/
├── pages/                           # Next.js pages
│   ├── index.tsx                    # Dashboard (auto-refresh)
│   ├── articles/                    # Article list & detail
│   ├── analytics/                   # Analytics dashboard
│   ├── admin/ingest.tsx             # Ingest admin panel
│   └── api/                         # Next.js API routes (proxy to FastAPI)
├── components/                      # React components
├── src/financial_news/              # Python backend
│   ├── api/main.py                  # FastAPI app + routes
│   ├── services/
│   │   ├── news_ingest.py           # RSS feed ingestion (18+ feeds)
│   │   ├── continuous_runner.py     # Background ingestion loop
│   │   ├── content_extractor.py     # HTTP article text extraction
│   │   └── connectors/              # Public API connectors
│   │       ├── gdelt.py             # GDELT v2 DOC API
│   │       ├── sec_edgar.py         # SEC EDGAR + press RSS
│   │       └── newsdata.py          # Newsdata.io (optional)
│   ├── storage/                     # PostgreSQL models & repositories
│   └── core/                        # Sentiment, summarizer, config
├── tests/unit/                      # Unit tests
├── docker-compose.yml               # PostgreSQL + app
├── Dockerfile                       # Full production image
├── run_server.py                    # Dev server (FastAPI + Next.js)
└── .env.example                     # All configuration documented
```

## ⚙️ Configuration

All config is via environment variables. See [`.env.example`](.env.example) for the full list. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection string |
| `CONTINUOUS_INGEST_ENABLED` | `true` | Enable background ingestion loop |
| `CONTINUOUS_INGEST_INTERVAL_SECONDS` | `300` | Seconds between ingestion cycles |
| `GDELT_ENABLED` | `true` | Enable GDELT connector |
| `SEC_EDGAR_ENABLED` | `true` | Enable SEC EDGAR connector |
| `NEWSDATA_ENABLED` | `true` | Enable Newsdata.io (needs API key) |
| `NEWSDATA_API_KEY` | _(empty)_ | Newsdata.io free tier key |

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, code style, and PR process.

The easiest way to contribute is **adding a new data source connector** — see the guide in CONTRIBUTING.md.

## 📄 License

[MIT](LICENSE) © Fernando Gonzalez
