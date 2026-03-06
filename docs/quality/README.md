# Quality Baseline and Ratchet

This project uses a **no-regression quality ratchet** while existing debt is burned down incrementally.

## Ratchet Configuration

Thresholds and critical modules are defined in:

- `config/quality-baseline.json`

The scorecard includes both repo-wide debt and active-module debt:

- `active_module_ruff_errors`
- `active_module_mypy_errors`

Active modules are currently:

- `src/financial_news/api/main.py`
- `src/financial_news/services/news_ingest.py`
- `src/financial_news/services/continuous_runner.py`
- `src/financial_news/storage/repositories.py`

## Commands

Collect current metrics:

```bash
python scripts/quality_checkpoint.py collect \
  --output-json output/quality/current.json \
  --output-md output/quality/current.md
```

Run ratchet checks:

```bash
python scripts/quality_checkpoint.py ratchet \
  --baseline config/quality-baseline.json \
  --current output/quality/current.json
```

Legacy compatibility scripts still exist under `scripts/quality/` and at the
repo root, but `scripts/quality_checkpoint.py` is the canonical path used by CI.

## CI Integration

CI runs the ratchet checks and uploads baseline artifacts so trends can be tracked over time.
