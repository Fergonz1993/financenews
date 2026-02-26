# Repository Guidelines

## Project Structure & Module Organization
This repo is a **hybrid platform**:

- `pages/`, `components/`, `styles/`, and root-level `next.config.js`: Next.js app (TypeScript + API routes under `pages/api/`).
- `src/financial_news/`: Core Python package with API, services, dashboard, CLI, and core analysis engines.
- `tests/`: Python tests (`tests/unit/`, `tests/integration/`) + `tests/conftest.py`.
- `docs/`, `scripts/`, `config/`, `run_server.py`, and `docker-compose.yml` for local orchestration/reference.

## Build, Test, and Development Commands
- **Next.js (root)**:
  - `bun install` (or `npm install` if preferred) installs dependencies.
  - `bun run dev` starts the frontend app at `http://localhost:3000`.
  - `bun run build` builds production assets.
  - `bun run lint` runs ESLint.
- **Python backend (root)**:
  - `pip install -e ".[dev]"` installs runtime + dev tools.
  - `make test` runs full pytest suite.
  - `make test-unit` runs `tests/unit`.
  - `make test-integration` runs `tests/integration`.
  - `make lint` runs static checks; `make format` applies formatters.
  - `make run-api`, `make run-dashboard`, `make run-cli` start respective entrypoints.
  - `python run_server.py` starts both backend (`uvicorn`) and Next.js frontend.
  - `docker-compose up --build` runs the full stack (app, dashboard, redis, mongo, scheduler).
- Use `make help` to list backend shortcuts.

## Coding Style & Naming Conventions
- TypeScript/React: follow existing style (2-space indentation, semicolons, PascalCase components, camelCase variables/functions).
- Python: prefer typed code, explicit names, and modern async patterns.
- Python formatting/linting targets are configured for:
  - Black (line length 88),
  - Ruff/ES lint-style checks,
  - strict mypy style constraints in `pyproject.toml`.
- Keep API paths and filenames descriptive (`pages/api/<feature>.ts`, `src/financial_news/<domain>/`).

## Testing Guidelines
- Frameworks: `pytest` (Python).
- Naming:
  - Files: `test_*.py` or `*_test.py`.
  - Test classes: `Test*`.
  - Test functions: `test_*`.
- Run targeted tests before opening PRs: e.g. `pytest tests/unit/test_article.py`.

## Commit & Pull Request Guidelines
- Use existing commit convention from history: imperative lower-case subjects (e.g., `feat:`, `chore:`, `fix:`).
- Prefer single-purpose commits with a clear scope.
- PRs should include:
  - concise summary and rationale,
  - commands executed (`make test`, `bun run lint`, etc.),
  - linked issue or context,
  - screenshots for UI-facing changes,
  - any env/config updates required.

## Security & Configuration Tips
- Never commit credentials/API keys.
- Copy `.env.example` (if available) and create environment-specific `.env` locally.
- Confirm backend and frontend URLs before pushing (`NEXT_PUBLIC_API_URL`, backend host/port, API keys).
