# Frontend Reliability Runbook

## Purpose
This runbook covers how the Next.js frontend behaves when the FastAPI backend is unavailable and how to run the production-style smoke + screenshot regression suite.

## Reliability Model
The Next API routes in `pages/api/*` follow this order:

1. Try FastAPI backend (primary source of truth).
2. If backend is unreachable (`502` connectivity failure), switch to local fallback data from `data/`.
3. Preserve stable response contracts so frontend pages remain usable.

Fallback data sources:

- `data/ingested_articles.json`
- `data/articles.json` (secondary)
- `data/sources.json` (for crawler admin fallback)
- `data/saved_articles/*.json` (offline saved-article toggles)

## Health Endpoint
Use `GET /api/health` to inspect mode and data source status.

Possible modes:

- `backend`: FastAPI reachable.
- `fallback`: FastAPI unreachable, local data fallback active.
- `degraded`: neither backend nor usable local fallback data is available.

## Environment Variables
Use these for reliability tuning:

- `FASTAPI_URL`: absolute FastAPI URL for server-side proxy routes.
- `ENABLE_LOCAL_API_FALLBACK`: `true` (default) or `false` to disable fallback.
- `FASTAPI_REQUEST_TIMEOUT_MS`: upstream request timeout (default `8000`).
- `FASTAPI_GET_RETRIES`: retry count for GET proxy requests (default `1`).

## Local Verification
Run full smoke + screenshot regression:

```bash
bun run smoke
```

What it does:

1. Builds Next.js in production mode.
2. Starts `next start`.
3. Runs API/route contract checks.
4. Captures desktop + mobile screenshots.

Artifacts:

- Logs: `.tmp/smoke/`
- Screenshots: `output/playwright/smoke/`

## Debugging 502s
If you still see `502` in API responses:

1. Check `GET /api/health`.
2. If mode is `fallback`, verify `data/ingested_articles.json` exists and is valid JSON.
3. If mode is `degraded`, either:
   - start FastAPI (`uvicorn financial_news.api.main:app --host 127.0.0.1 --port 8000`), or
   - regenerate local data via ingest scripts.
4. Check frontend logs in `.tmp/smoke/frontend.log` for route-level failures.

## CI Gate
Workflow: `.github/workflows/frontend-reliability.yml`

CI enforces:

1. `bun run lint`
2. `bun run smoke`
3. Artifact upload for logs and screenshot regression output
