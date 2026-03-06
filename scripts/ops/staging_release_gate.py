#!/usr/bin/env python3
"""Run a deterministic staging release gate.

Gate sequence:
1. Apply migrations to head.
2. Verify rollback path with downgrade -1 then re-upgrade head.
3. Run deterministic integration tests.
4. Run quality checkpoint + ratchet.
5. Optionally run frontend smoke checks.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class StepResult:
    name: str
    command: str
    return_code: int
    duration_seconds: float
    stdout: str
    stderr: str


def _run(command: list[str], *, env: dict[str, str]) -> StepResult:
    started = time.monotonic()
    proc = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    finished = time.monotonic()
    return StepResult(
        name=" ".join(command[:2]),
        command=" ".join(shlex.quote(part) for part in command),
        return_code=proc.returncode,
        duration_seconds=round(finished - started, 3),
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def _make_env(database_url: str) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", "src")
    env["DATABASE_URL"] = database_url
    venv_bin = Path(".venv/bin")
    if venv_bin.exists():
        env["PATH"] = f"{venv_bin}:{env.get('PATH', '')}"
    return env


def _serialize_step(step: StepResult) -> dict[str, Any]:
    return {
        "name": step.name,
        "command": step.command,
        "return_code": step.return_code,
        "duration_seconds": step.duration_seconds,
        "stdout_tail": step.stdout[-4000:],
        "stderr_tail": step.stderr[-4000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run staging release gate checks")
    parser.add_argument(
        "--database-url",
        default=os.getenv("STAGING_DATABASE_URL") or os.getenv("DATABASE_URL") or "",
        help="Database URL used for migration checks",
    )
    parser.add_argument(
        "--skip-rollback-check",
        action="store_true",
        help="Skip downgrade -1 and re-upgrade migration check",
    )
    parser.add_argument(
        "--run-smoke",
        action="store_true",
        help="Run bun smoke suite as final gate",
    )
    parser.add_argument(
        "--output-json",
        default="output/ops/staging-gate-report.json",
        help="JSON report output path",
    )
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit(
            "Missing database URL. Set STAGING_DATABASE_URL or pass --database-url."
        )

    env = _make_env(args.database_url)
    report_steps: list[StepResult] = []

    commands: list[tuple[str, list[str]]] = [
        ("migration_upgrade_head", ["alembic", "upgrade", "head"]),
    ]
    if not args.skip_rollback_check:
        commands.extend(
            [
                ("migration_downgrade_one", ["alembic", "downgrade", "-1"]),
                ("migration_reupgrade_head", ["alembic", "upgrade", "head"]),
            ]
        )
    commands.extend(
        [
            (
                "integration_tests",
                ["pytest", "tests/integration", "-q", "-m", "integration"],
            ),
            (
                "quality_collect",
                [
                    sys.executable,
                    "scripts/quality_checkpoint.py",
                    "collect",
                    "--output-json",
                    "output/quality/current.json",
                    "--output-md",
                    "output/quality/current.md",
                ],
            ),
            (
                "quality_ratchet",
                [
                    sys.executable,
                    "scripts/quality_checkpoint.py",
                    "ratchet",
                    "--baseline",
                    "config/quality-baseline.json",
                    "--current",
                    "output/quality/current.json",
                ],
            ),
        ]
    )
    if args.run_smoke:
        commands.append(("frontend_smoke", ["bun", "run", "smoke"]))

    failed_step = None
    for step_name, command in commands:
        result = _run(command, env=env)
        result.name = step_name
        report_steps.append(result)
        if result.return_code != 0:
            failed_step = step_name
            break

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "database_url_redacted": args.database_url.rsplit("@", 1)[-1],
        "run_smoke": bool(args.run_smoke),
        "rollback_check_enabled": not bool(args.skip_rollback_check),
        "status": "failed" if failed_step else "passed",
        "failed_step": failed_step,
        "steps": [_serialize_step(step) for step in report_steps],
    }

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 1 if failed_step else 0


if __name__ == "__main__":
    raise SystemExit(main())
