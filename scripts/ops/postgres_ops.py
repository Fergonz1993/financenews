#!/usr/bin/env python3
"""PostgreSQL backup/restore helpers with restore-drill support."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import SplitResult, urlsplit, urlunsplit


@dataclass(slots=True)
class CommandResult:
    command: str
    return_code: int
    stdout: str
    stderr: str
    duration_seconds: float


def _run(command: list[str], *, check: bool = True) -> CommandResult:
    started = time.monotonic()
    proc = subprocess.run(command, check=False, capture_output=True, text=True)
    finished = time.monotonic()
    result = CommandResult(
        command=" ".join(shlex.quote(part) for part in command),
        return_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        duration_seconds=round(finished - started, 3),
    )
    if check and result.return_code != 0:
        raise RuntimeError(
            f"Command failed ({result.return_code}): {result.command}\n"
            f"STDOUT:\n{result.stdout[-3000:]}\nSTDERR:\n{result.stderr[-3000:]}"
        )
    return result


def _ensure_database_url(value: str | None) -> str:
    if value and value.strip():
        return value.strip()
    raise RuntimeError("A PostgreSQL URL is required.")


def _require_commands(*names: str) -> None:
    missing = [name for name in names if shutil.which(name) is None]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Missing required PostgreSQL CLI tools: {joined}. "
            "Install PostgreSQL client binaries and retry."
        )


def _db_name(database_url: str) -> str:
    parsed = urlsplit(database_url)
    name = parsed.path.lstrip("/")
    if not name:
        raise RuntimeError("Database URL must include a database name.")
    return name


def _with_database(database_url: str, database_name: str) -> str:
    parsed: SplitResult = urlsplit(database_url)
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            f"/{database_name}",
            parsed.query,
            parsed.fragment,
        )
    )


def _reset_database(database_url: str) -> None:
    target_db = _db_name(database_url)
    safe_db_literal = target_db.replace("'", "''")
    safe_db_ident = target_db.replace('"', '""')
    admin_url = _with_database(database_url, "postgres")

    _run(
        [
            "psql",
            admin_url,
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            (
                "SELECT pg_terminate_backend(pid) "
                f"FROM pg_stat_activity WHERE datname = '{safe_db_literal}' "
                "AND pid <> pg_backend_pid();"
            ),
        ]
    )
    _run(
        [
            "psql",
            admin_url,
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            f'DROP DATABASE IF EXISTS "{safe_db_ident}";',
        ]
    )
    _run(
        [
            "psql",
            admin_url,
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            f'CREATE DATABASE "{safe_db_ident}";',
        ]
    )


def _backup(database_url: str, output_dir: Path, retention_days: int) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    backup_path = output_dir / f"financenews-{stamp}.dump"

    _run(
        [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--dbname",
            database_url,
            "--file",
            str(backup_path),
        ]
    )

    cutoff = datetime.now(UTC) - timedelta(days=max(1, retention_days))
    for candidate in output_dir.glob("financenews-*.dump"):
        modified_at = datetime.fromtimestamp(candidate.stat().st_mtime, tz=UTC)
        if modified_at < cutoff and candidate != backup_path:
            candidate.unlink(missing_ok=True)

    return backup_path


def _restore(backup_file: Path, target_database_url: str, *, recreate_target: bool) -> None:
    if not backup_file.exists():
        raise RuntimeError(f"Backup file does not exist: {backup_file}")

    if recreate_target:
        _reset_database(target_database_url)

    _run(
        [
            "pg_restore",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "--dbname",
            target_database_url,
            str(backup_file),
        ]
    )


def _drill(source_database_url: str, target_database_url: str, output_json: Path) -> dict[str, object]:
    started = time.monotonic()
    backup_dir = Path("output/ops/backups")
    backup_file = _backup(source_database_url, backup_dir, retention_days=7)
    _restore(backup_file, target_database_url, recreate_target=True)

    table_count_result = _run(
        [
            "psql",
            target_database_url,
            "-tA",
            "-c",
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';",
        ]
    )
    table_count = int((table_count_result.stdout or "0").strip() or "0")
    finished = time.monotonic()

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_database": _db_name(source_database_url),
        "target_database": _db_name(target_database_url),
        "backup_file": str(backup_file),
        "table_count_after_restore": table_count,
        "duration_seconds": round(finished - started, 3),
        "status": "passed" if table_count > 0 else "failed",
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="PostgreSQL backup/restore operations")
    sub = parser.add_subparsers(dest="command", required=True)

    backup = sub.add_parser("backup", help="Create a Postgres backup")
    backup.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Source PostgreSQL database URL",
    )
    backup.add_argument(
        "--output-dir",
        default="output/ops/backups",
        help="Backup output directory",
    )
    backup.add_argument(
        "--retention-days",
        type=int,
        default=7,
        help="Delete backups older than this many days",
    )

    restore = sub.add_parser("restore", help="Restore a backup into a target database")
    restore.add_argument("--backup-file", required=True, help="Path to .dump file")
    restore.add_argument(
        "--target-database-url",
        default=os.getenv("RESTORE_DATABASE_URL"),
        help="Target PostgreSQL database URL",
    )
    restore.add_argument(
        "--recreate-target",
        action="store_true",
        help="Drop and recreate target database before restore",
    )

    drill = sub.add_parser(
        "drill",
        help="Run a timed backup+restore drill against a staging target DB",
    )
    drill.add_argument(
        "--source-database-url",
        default=os.getenv("DATABASE_URL"),
        help="Source production/staging URL to back up",
    )
    drill.add_argument(
        "--target-database-url",
        default=os.getenv("DRILL_DATABASE_URL"),
        help="Target URL where backup will be restored",
    )
    drill.add_argument(
        "--output-json",
        default="output/ops/restore-drill-report.json",
        help="Restore drill report path",
    )

    args = parser.parse_args()

    if args.command == "backup":
        _require_commands("pg_dump")
        database_url = _ensure_database_url(args.database_url)
        backup_file = _backup(
            database_url,
            Path(args.output_dir),
            retention_days=max(1, int(args.retention_days)),
        )
        print(json.dumps({"backup_file": str(backup_file)}, indent=2))
        return 0

    if args.command == "restore":
        _require_commands("pg_restore", "psql")
        target = _ensure_database_url(args.target_database_url)
        _restore(Path(args.backup_file), target, recreate_target=bool(args.recreate_target))
        print(
            json.dumps(
                {
                    "status": "restored",
                    "target_database": _db_name(target),
                    "backup_file": args.backup_file,
                },
                indent=2,
            )
        )
        return 0

    _require_commands("pg_dump", "pg_restore", "psql")
    source = _ensure_database_url(args.source_database_url)
    target = _ensure_database_url(args.target_database_url)
    report = _drill(source, target, Path(args.output_json))
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
