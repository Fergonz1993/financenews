# Ralph Loop Task Contract

## Mission

Ship reliability-first acceleration for Financenews with deterministic gates, hardened ingestion contracts, and controlled feature rollout.

## Operating Rule

Every iteration must:

1. Pick the highest-impact unresolved reliability item.
2. Implement the smallest complete change that moves that item to done.
3. Run `VERIFY_CMD` and only mark progress if it passes.
4. Record one high-level principled meta-lesson in compounding notes.

## Priority Backlog (Execution Order)

1. - [x] Keep CI merge-gates deterministic (lint/type/unit/integration/smoke/ratchet).
2. - [x] Raise critical-path backend coverage (`api/main.py`, ingestion services, repositories).
3. - [x] Enforce typed ingestion boundaries and strict connector validation.
4. - [x] Lock API contracts (`/api/articles`, `/api/analytics`, `/api/sources`, `/api/ingest/status`).
5. - [x] Harden admin mutation security (auth/rbac/rate-limit/audit trail).
6. - [x] Preserve idempotency + replay safety in ingestion/state transitions.
7. Maintain connector feature flags + runtime kill switches.
8. Keep staging gate + backup/restore drills green.
9. - [x] Improve ranking/dedup quality with measurable duplicate-rate reduction.
10. Ship new connector/enrichment work behind safe flags and fail-open behavior.

## Default Verify Command

Use this unless explicitly overridden:

```bash
bun run typecheck && bun run lint && \
PYTHONPATH=src .venv/bin/pytest tests/unit -q && \
PYTHONPATH=src .venv/bin/pytest tests/integration -q -m integration && \
.venv/bin/python scripts/quality_checkpoint.py collect --output-json output/quality/current.json --output-md output/quality/current.md && \
.venv/bin/python scripts/quality_checkpoint.py ratchet --baseline config/quality-baseline.json --current output/quality/current.json
```
