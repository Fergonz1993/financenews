# CLAUDE.md

This file provides guidance for AI assistants working with the Financial News codebase.

## Project Overview

Financial News is an AI-powered financial news analysis and summarization platform. It has two main parts:

1. **Next.js frontend** (TypeScript/React) — pages, API routes, and UI components
2. **Python backend** (`src/financial_news/`) — FastAPI server, CLI, sentiment analysis, summarization, and data processing engines

The project uses OpenAI GPT-4o-mini for AI analysis, transformer models for NLP, and aggregates news from NewsAPI, Finnhub, and RSS feeds.

## Repository Structure

```
financenews/
├── src/financial_news/       # Python package (main backend)
│   ├── config/               # Settings and logging
│   ├── core/                 # Sentiment analysis, summarization
│   ├── models/               # Data models (Article, etc.)
│   ├── api/                  # FastAPI endpoints, WebSocket handlers
│   ├── cli/                  # Click-based CLI
│   ├── services/             # Streaming, automation, WebSocket services
│   ├── dashboard/            # Streamlit dashboard + visualization
│   ├── analytics/            # Advanced analytics engine
│   ├── intelligence/         # NLP engine
│   ├── portfolio/            # Portfolio management
│   ├── market_data/          # Real-time market data engine
│   ├── economics/            # Macro analysis engine
│   ├── trading/              # Algorithmic trading engine
│   ├── risk/                 # Risk management engine
│   ├── security/             # Enterprise security
│   └── collaboration/        # Collaboration engine
├── src/services/crawler/     # TypeScript web crawler (RSS, API, web)
├── pages/                    # Next.js pages (articles, analytics, admin)
│   └── api/                  # Next.js API routes
├── components/               # Shared React components (Layout, Navigation, NotificationCenter)
├── context/                  # React Context providers (Theme, Notifications)
├── styles/                   # Global CSS
├── utils/                    # TypeScript utilities (fetcher)
├── frontend/                 # Secondary standalone React app
│   └── src/                  # Components, pages, API layer, context
├── tests/                    # Python test suite
│   ├── unit/                 # Unit tests
│   └── integration/          # Integration tests
├── config/                   # config.yaml and env_template
├── scripts/                  # Python setup and optimization scripts
├── docs/                     # Project documentation
├── briefings/                # Auto-generated markdown briefing reports
└── requirements/             # Modular Python requirements (base, dev, ml)
```

## Tech Stack

### Python Backend
- **Python >= 3.10** (required)
- **FastAPI + Uvicorn** for the REST API (port 8000)
- **Pydantic** for request/response models
- **OpenAI SDK** for GPT-4o-mini summarization
- **TextBlob / Transformers** for sentiment analysis
- **pandas, numpy, matplotlib, seaborn** for data analysis
- **Redis** for caching, **MongoDB** for persistence
- **Click** for CLI, **Rich** for terminal output
- **aiohttp, httpx, websockets** for async HTTP and WebSocket

### Next.js Frontend
- **Next.js 13.5.6** with **React 18** and **TypeScript 5**
- **Material-UI (MUI) 5** for component library
- **Chart.js + react-chartjs-2** for data visualizations
- **SWR** for data fetching with caching
- **Axios** for HTTP requests
- **Socket.io** for real-time WebSocket connections

### Infrastructure
- **Docker + Docker Compose** (app, dashboard, redis, mongo, scheduler services)
- **Pre-commit hooks** for code quality enforcement

## Development Commands

### Next.js Frontend
```bash
npm install          # Install dependencies
npm run dev          # Start dev server (localhost:3000)
npm run build        # Production build
npm run start        # Start production server
npm run lint         # ESLint
```

### Python Backend (via Makefile)
```bash
make install         # pip install -e .
make install-dev     # pip install -e ".[dev]" + pre-commit install
make test            # pytest tests/ -v
make test-unit       # pytest tests/unit/ -v
make test-integration # pytest tests/integration/ -v
make lint            # flake8 src/ tests/ && mypy src/
make format          # black + isort + autoflake on src/ and tests/
make clean           # Remove __pycache__, .egg-info, build/dist
make run-api         # python -m financial_news.api.main
make run-dashboard   # python -m financial_news.dashboard.app
make run-cli         # python -m financial_news.cli.main
make docs            # mkdocs build
make build           # python -m build
```

### Docker
```bash
docker-compose up              # Start all services (app, dashboard, redis, mongo, scheduler)
docker-compose up app           # Start just the API service
docker-compose up -d            # Start detached
```

## Code Style and Conventions

### Python
- **Formatter**: Black (line length 88)
- **Linter**: Ruff (replaces flake8 + isort + more). Rules: E, W, F, I, B, C4, UP, SIM, PERF, RUF
- **Type checker**: MyPy (strict mode — `disallow_untyped_defs`, `disallow_incomplete_defs`, `strict_equality`)
- **Target Python**: 3.10+ (use `|` union syntax, not `Union[]`)
- **Imports**: sorted by isort via Ruff (I rules)
- **Docstrings**: module-level and class-level docstrings are used throughout
- **Settings**: dataclass-based configuration in `src/financial_news/config/settings.py`, loaded from environment variables
- **Naming**: snake_case for functions/variables, PascalCase for classes, ALL_CAPS for constants

### TypeScript/React
- **Strict mode** enabled in tsconfig.json
- **ESLint** with `eslint-config-next`
- **Path aliases**: `@/*` maps to project root
- **Component files**: `.tsx` for React components, `.ts` for utilities
- **Pages**: Next.js file-based routing in `pages/`
- **API routes**: Next.js API routes in `pages/api/`
- **Theming**: MUI ThemeProvider with dark/light mode toggle
- **State management**: React Context API (ThemeContext, NotificationContext)

## Testing

### Python Tests
- **Framework**: pytest with strict markers and strict config
- **Test paths**: `tests/unit/` and `tests/integration/`
- **Naming**: files must match `test_*.py` or `*_test.py`; functions must match `test_*`; classes must match `Test*`
- **Markers**: `slow`, `integration`, `unit`
- **Fixtures**: defined in `tests/conftest.py` — provides `test_settings`, `sample_news_data`, `sample_market_data`, `mock_api_response`
- **Coverage**: measured on `src/`, excludes test files
- **Async tests**: supported via `pytest-asyncio`

Run tests:
```bash
make test              # All tests
make test-unit         # Unit tests only
make test-integration  # Integration tests only
pytest tests/ -v --cov=src  # With coverage
```

## Pre-commit Hooks

The following hooks run automatically on commit (configured in `.pre-commit-config.yaml`):

1. **pre-commit-hooks**: trailing-whitespace, end-of-file-fixer, check-yaml/toml/json, check-added-large-files (1MB max), debug-statements, name-tests-test
2. **Black**: Python formatting (line-length 88)
3. **Ruff**: Linting + import sorting (with `--fix`)
4. **MyPy**: Static type checking (with types-requests, types-PyYAML, types-redis)
5. **Bandit**: Security scanning (excludes tests/)
6. **Codespell**: Spell checking (auto-fix with `--write-changes`)
7. **Pyupgrade**: Upgrade syntax to Python 3.10+
8. **Autoflake**: Remove unused imports and variables
9. **validate-pyproject**: Validate pyproject.toml
10. **add-trailing-comma**: Add trailing commas (py36+)
11. **safety**: Check requirements files for known vulnerabilities
12. **nbQA**: Black + Ruff for Jupyter notebooks

## Environment Variables

Key environment variables (see `.env.example` and `config/env_template`):

```
ALPHA_VANTAGE_API_KEY    # Alpha Vantage market data
FINNHUB_API_KEY          # Finnhub financial data
NEWS_API_KEY             # NewsAPI news aggregation
POLYGON_API_KEY          # Polygon market data
DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD  # PostgreSQL
REDIS_HOST               # Redis cache
MONGO_URI                # MongoDB connection string
ENVIRONMENT              # development / production / test
DEBUG                    # true / false
API_HOST / API_PORT      # FastAPI server binding
WS_HOST / WS_PORT        # WebSocket server binding
SENTIMENT_MODEL          # ML model for sentiment (default: finbert)
SUMMARIZATION_MODEL      # ML model for summaries (default: facebook/bart-large-cnn)
NEXT_PUBLIC_API_URL      # Frontend API base URL (default: /api)
NEXT_PUBLIC_WS_URL       # Frontend WebSocket URL
```

## Configuration

- **Python config**: `config/config.yaml` — defines tracked queries (stock tickers, topics), AI model settings, data source toggles, processing limits, analysis features, scheduling cron, and content filters
- **Settings class**: `src/financial_news/config/settings.py` — dataclass hierarchy (`Settings`, `DatabaseConfig`, `APIConfig`, `NewsSourcesConfig`, `MLConfig`, `WebSocketConfig`). Loaded from env vars via `Settings.from_env()` or from TOML via `Settings.from_toml()`
- **Next.js config**: `next.config.js` — strict mode, SWC minify, image optimization, removes console.log in production

## Key Architecture Decisions

- The Python backend is installed as an editable package (`pip install -e .`) with the entry point `financial-news` mapped to `financial_news.cli:main`
- The project has two frontend implementations: the primary Next.js app (in `pages/`, `components/`, `context/`) and a secondary standalone React app (in `frontend/`). The Next.js app is the active frontend
- Next.js API routes (`pages/api/`) serve as a BFF (backend-for-frontend) layer, while the FastAPI server (`src/financial_news/api/main.py`) is the primary Python API
- The TypeScript crawler system (`src/services/crawler/`) provides RSS, API, and web crawling capabilities with a scheduler
- Docker Compose orchestrates five services: app (FastAPI on 8000), dashboard (Streamlit on 8501), redis (6379), mongo (27017), and scheduler

## Common Tasks for AI Assistants

### Adding a new Python module
1. Create the module under the appropriate `src/financial_news/` subdirectory
2. Add an `__init__.py` if creating a new subpackage
3. Follow existing patterns: dataclass for configs, type annotations on all functions, module-level docstring
4. Add tests in `tests/unit/` or `tests/integration/`
5. Run `make format && make lint && make test` to verify

### Adding a new Next.js page
1. Create the page file in `pages/` following Next.js file-based routing
2. Use MUI components and the existing Layout component
3. Use SWR or Axios for data fetching
4. Add corresponding API routes in `pages/api/` if needed

### Adding a new API endpoint (Python)
1. Add the route in `src/financial_news/api/main.py` or create a new route file under `src/financial_news/api/routes/`
2. Define Pydantic request/response models
3. Follow the existing pattern: async endpoint functions, proper HTTP status codes, HTTPException for errors

### Running the full stack locally
1. Start Python API: `make run-api` (port 8000)
2. Start Next.js dev server: `npm run dev` (port 3000)
3. Or use Docker: `docker-compose up`
