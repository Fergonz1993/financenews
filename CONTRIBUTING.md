# Contributing to Financial News

Thanks for your interest in contributing! This guide will help you get set up.

## Development Setup

### Prerequisites

- **Python 3.12+** with `uv` or `pip`
- **Node.js 20+** with `bun`
- **PostgreSQL 16+** (or use Docker)

### Quick Start

```bash
# Clone
git clone https://github.com/Fergonz1993/financenews.git
cd financenews

# Backend
cp .env.example .env          # edit DB credentials if needed
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Database
createdb financenews           # or use docker-compose up postgres

# Frontend
bun install

# Run everything
python run_server.py           # starts FastAPI + Next.js
```

### Or use Docker

```bash
docker compose up --build
```

## Running Tests

```bash
# Python unit tests
PYTHONPATH=src .venv/bin/pytest tests/unit -v

# Deterministic integration tests
PYTHONPATH=src .venv/bin/pytest tests/integration -v -m integration

# TypeScript type check
bun run typecheck

# Quality checkpoint + ratchet (no regression)
.venv/bin/python scripts/quality_checkpoint.py collect --output-json output/quality/current.json --output-md output/quality/current.md
.venv/bin/python scripts/quality_checkpoint.py ratchet --baseline config/quality-baseline.json --current output/quality/current.json

# Frontend smoke and screenshot regression
bun run smoke

# Staging gate + operational drills
make staging-gate
make db-backup
make db-restore-drill
```

## Project Structure

```
src/financial_news/          # Python backend
├── api/                     # FastAPI routes
├── services/                # Business logic
│   ├── connectors/          # GDELT, SEC EDGAR, Newsdata.io
│   ├── continuous_runner.py # Background ingestion loop
│   ├── content_extractor.py # HTTP-based article extraction
│   └── news_ingest.py       # RSS feed ingestion
├── storage/                 # PostgreSQL models & repos
└── core/                    # Sentiment analysis, summarizer

pages/                       # Next.js frontend
components/                  # React components
```

## Code Style

- **Python**: [Black](https://github.com/psf/black) + [Ruff](https://github.com/astral-sh/ruff)
- **TypeScript**: [ESLint](https://eslint.org/) with the project config

Run formatters and quality gates before committing:

```bash
.venv/bin/ruff check src/ tests/ --fix
.venv/bin/ruff format src/ tests/
make quality-ratchet
```

## Pull Request Process

1. **Fork** the repo and create a branch from `main`
2. **Write tests** for any new functionality
3. **Run the full test suite** — all tests must pass
4. **Keep commits clean** — use descriptive commit messages
5. **Open a PR** with a clear description of what changed and why

## Adding New Data Sources

The easiest way to contribute is by adding a new connector:

1. Create a file in `src/financial_news/services/connectors/`
2. Follow the pattern in `gdelt.py` — implement `fetch_articles()` returning a list of dicts
3. Register it in `continuous_runner.py`
4. Add tests in `tests/unit/test_connectors.py`
5. Add any required env vars to `.env.example`

## Reporting Issues

- Use [GitHub Issues](https://github.com/Fergonz1993/financenews/issues)
- Include steps to reproduce, expected behavior, and your environment
- For security issues, email directly instead of opening a public issue

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
