# Backup and Restore Drill

This runbook defines automated backup and restore drill operations for PostgreSQL.

## Targets

- RPO target: `<= 24h`
- RTO target (drill): `<= 20 minutes`

## Prerequisites

- PostgreSQL client binaries installed and available on `PATH`:
  - `pg_dump`
  - `pg_restore`
  - `psql`
- Quick check:

```bash
pg_dump --version && pg_restore --version && psql --version
```

## Commands

Create a backup:

```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/financenews"
PATH=".venv/bin:$PATH" .venv/bin/python scripts/ops/postgres_ops.py backup \
  --database-url "$DATABASE_URL" \
  --output-dir output/ops/backups \
  --retention-days 7
```

Restore backup into a target database:

```bash
export RESTORE_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/financenews_restore"
PATH=".venv/bin:$PATH" .venv/bin/python scripts/ops/postgres_ops.py restore \
  --backup-file output/ops/backups/financenews-YYYYMMDD-HHMMSS.dump \
  --target-database-url "$RESTORE_DATABASE_URL" \
  --recreate-target
```

Run a full timed restore drill:

```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/financenews"
export DRILL_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/financenews_drill"
PATH=".venv/bin:$PATH" .venv/bin/python scripts/ops/postgres_ops.py drill \
  --source-database-url "$DATABASE_URL" \
  --target-database-url "$DRILL_DATABASE_URL" \
  --output-json output/ops/restore-drill-report.json
```

## Drill success criteria

1. Report status is `passed`.
2. `table_count_after_restore` is greater than zero.
3. `duration_seconds` meets the RTO target.
4. Drill report is archived with release artifacts.
