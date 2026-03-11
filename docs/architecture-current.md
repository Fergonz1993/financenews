# Current Architecture

## Runtime Truth
Financenews is currently a hybrid application with one canonical backend data plane.

### Request path
1. **Next.js pages** render the operator and analyst-facing UI.
2. **Next.js API routes** proxy browser requests to the backend and provide degraded read-only fallback when the backend is unavailable.
3. **FastAPI** is the canonical application backend and source registry/control plane.
4. **PostgreSQL** is the system of record for articles, source metadata, ingestion state, and user settings.

## Major Runtime Components

### Frontend
- `pages/`
- `components/`
- `pages/api/*`

Responsibilities:

- render dashboards and admin views,
- maintain stable browser-facing envelopes,
- mark whether data came from `backend`, `fallback_read_only`, or `degraded` mode.

### Backend
- `src/financial_news/api/`
- `src/financial_news/services/`
- `src/financial_news/storage/`

Responsibilities:

- ingest and normalize articles,
- manage connector/source state,
- expose stable REST and websocket contracts,
- compute freshness and health metadata.

### Persistence
- PostgreSQL via SQLAlchemy models and repositories in `src/financial_news/storage/`

Canonical persisted concerns:

- articles,
- source registry,
- ingestion runs and ingestion state,
- user settings and saved-article state.

## Fallback Model
Local JSON fallback exists for **degraded read-only resilience**, not as a second authoritative control plane.

Allowed uses:

- read-only UI continuity,
- smoke/demo support,
- local diagnostics when the backend is down.

Not authoritative for:

- source mutations,
- scheduler control,
- ingest health interpretation,
- long-term state ownership.

## Architecture Direction
The current direction is:

- keep FastAPI + Next.js,
- reduce drift between backend contracts and frontend types,
- remove route dependence on `financial_news.api.main` globals,
- quarantine legacy duplicate crawler stacks from the active architecture,
- add agent-ready evidence and job interfaces only after the data substrate is trustworthy.
