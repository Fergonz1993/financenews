# Staging Release Gate

This gate enforces promotion discipline before production release.

## What the gate validates

1. `alembic upgrade head`
2. Rollback safety via `alembic downgrade -1` and re-upgrade to head
3. Deterministic integration tests (`tests/integration -m integration`)
4. Quality checkpoint + ratchet (`scripts/quality_checkpoint.py collect/ratchet`)
5. Optional frontend smoke suite (`bun run smoke`)

## Prerequisites

- `STAGING_DATABASE_URL` must point to a reachable PostgreSQL database.
- Python and Bun dependencies must be installed (`pip install -e ".[dev]"` and `bun install`).

## Run locally

```bash
export STAGING_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/financenews_staging"
PATH=".venv/bin:$PATH" .venv/bin/python scripts/ops/staging_release_gate.py \
  --database-url "$STAGING_DATABASE_URL" \
  --output-json output/ops/staging-gate-report.json
```

With smoke checks:

```bash
PATH=".venv/bin:$PATH" .venv/bin/python scripts/ops/staging_release_gate.py \
  --database-url "$STAGING_DATABASE_URL" \
  --run-smoke \
  --output-json output/ops/staging-gate-report.json
```

## Release checklist

1. `status` in `output/ops/staging-gate-report.json` is `passed`.
2. CI `quality-ratchet`, `python-tests`, and `frontend-smoke` jobs passed.
3. Connector override flags reviewed for rollout safety.
4. Restore drill executed in the last 7 days.
5. Rollback command tested on staging:
   - `alembic downgrade -1`
   - `alembic upgrade head`
