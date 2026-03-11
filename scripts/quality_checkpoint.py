#!/usr/bin/env python3
"""Collect and ratchet engineering quality metrics.

This script supports a staged quality strategy:
1. Collect current repo metrics (ruff/mypy/coverage/tsc/eslint/smoke)
2. Compare against a baseline and fail on regressions

Usage examples:
  .venv/bin/python scripts/quality_checkpoint.py collect --output-json output/quality/current.json --output-md output/quality/current.md
  .venv/bin/python scripts/quality_checkpoint.py ratchet --baseline config/quality-baseline.json --current output/quality/current.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import statistics
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LEGACY_ACTIVE_MODULE_PATHS = (
    "src/financial_news/api/api_management.py",
    "src/financial_news/api/main.py",
    "src/financial_news/core/summarizer.py",
    "src/financial_news/services/news_ingest.py",
    "src/financial_news/services/continuous_runner.py",
    "src/financial_news/storage/repositories.py",
)
ACTIVE_MODULE_DISCOVERY_PREFIXES = ("src/", "tests/")


@dataclass
class CommandResult:
    command: str
    return_code: int
    stdout: str
    stderr: str


def run_command(command: list[str]) -> CommandResult:
    try:
        process = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        missing = command[0] if command else "<unknown>"
        return CommandResult(
            command=" ".join(shlex.quote(part) for part in command),
            return_code=127,
            stdout="",
            stderr=f"{missing}: {exc}",
        )
    return CommandResult(
        command=" ".join(shlex.quote(part) for part in command),
        return_code=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
    )


def resolve_local_bin(executable: str) -> str:
    local = Path(sys.executable).parent / executable
    if local.exists() and local.is_file():
        return str(local)
    return executable


def _command_diagnostics(result: CommandResult, *, max_chars: int = 4000) -> dict[str, str]:
    if result.return_code == 0:
        return {}

    diagnostics: dict[str, str] = {}
    if result.stdout.strip():
        diagnostics["stdout_tail"] = result.stdout[-max_chars:]
    if result.stderr.strip():
        diagnostics["stderr_tail"] = result.stderr[-max_chars:]
    return diagnostics


def _normalize_repo_path(path: str) -> str:
    return path.strip().replace("\\", "/")


def _is_relevant_active_module(path: str) -> bool:
    normalized = _normalize_repo_path(path)
    return (
        bool(normalized)
        and normalized.endswith(".py")
        and any(
            normalized.startswith(prefix)
            for prefix in ACTIVE_MODULE_DISCOVERY_PREFIXES
        )
        and Path(normalized).exists()
    )


def _dedupe_paths(paths: list[str]) -> tuple[str, ...]:
    deduped: list[str] = []
    seen: set[str] = set()
    for path in paths:
        normalized = _normalize_repo_path(path)
        if normalized and normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)
    return tuple(deduped)


def _git_stdout_lines(command: list[str]) -> list[str]:
    result = run_command(command)
    if result.return_code != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _git_command_succeeds(command: list[str]) -> bool:
    return run_command(command).return_code == 0


def _git_has_head_parent() -> bool:
    return _git_command_succeeds(["git", "rev-parse", "--verify", "HEAD^"])


def discover_active_module_paths() -> tuple[str, ...]:
    discovered_paths: list[str] = []
    quality_base_ref = os.getenv("QUALITY_BASE_REF")
    quality_head_ref = os.getenv("QUALITY_HEAD_REF", "HEAD")

    if quality_base_ref:
        discovered_paths.extend(
            _git_stdout_lines(
                [
                    "git",
                    "diff",
                    "--name-only",
                    "--diff-filter=ACMRTUXB",
                    quality_base_ref,
                    quality_head_ref,
                ]
            )
        )

    discovered_paths.extend(
        _git_stdout_lines(["git", "diff", "--name-only", "--diff-filter=ACMRTUXB", "HEAD"])
    )
    discovered_paths.extend(
        _git_stdout_lines(
            [
                "git",
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "--diff-filter=ACMRTUXB",
                "-r",
                "HEAD",
            ]
        )
    )
    if _git_has_head_parent():
        discovered_paths.extend(
            _git_stdout_lines(
                ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB", "HEAD^", "HEAD"]
            )
        )
    discovered_paths.extend(
        _git_stdout_lines(["git", "ls-files", "--others", "--exclude-standard"])
    )

    changed_paths = _dedupe_paths(discovered_paths)
    relevant_paths = [
        path
        for path in changed_paths
        if _is_relevant_active_module(path)
    ]
    active_module_paths = _dedupe_paths(relevant_paths)
    if active_module_paths:
        return active_module_paths
    if changed_paths:
        return ()
    return LEGACY_ACTIVE_MODULE_PATHS


def parse_ruff_errors(output: str) -> int:
    if not output.strip():
        return 0
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return 0
    if isinstance(payload, list):
        return len(payload)
    return 0


def parse_ruff_errors_by_path(output: str, module_paths: tuple[str, ...]) -> dict[str, int]:
    counts = dict.fromkeys(module_paths, 0)
    if not output.strip():
        return counts
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return counts
    if not isinstance(payload, list):
        return counts

    normalized_paths = {
        key: key.replace("\\", "/")
        for key in module_paths
    }
    for issue in payload:
        if not isinstance(issue, dict):
            continue
        filename = str(issue.get("filename", "")).replace("\\", "/")
        if not filename:
            continue
        for original_path, normalized_path in normalized_paths.items():
            if filename.endswith(normalized_path):
                counts[original_path] += 1
    return counts


def parse_mypy_errors(output: str) -> int:
    return len(re.findall(r": error:", output))


def parse_mypy_errors_by_path(output: str, module_paths: tuple[str, ...]) -> dict[str, int]:
    counts = dict.fromkeys(module_paths, 0)
    normalized_paths = {
        key: key.replace("\\", "/")
        for key in module_paths
    }

    for line in output.splitlines():
        match = re.match(r"^(?P<path>[^:]+):\d+:\s+error:", line.strip())
        if not match:
            continue
        current = match.group("path").replace("\\", "/")
        for original_path, normalized_path in normalized_paths.items():
            if current.endswith(normalized_path):
                counts[original_path] += 1
                break
    return counts


def parse_pytest_coverage_pct(output: str) -> float | None:
    match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
    if not match:
        return None
    return float(match.group(1))


def parse_eslint_warnings(output: str) -> int:
    match = re.search(r"(\d+) warning", output)
    if match:
        return int(match.group(1))
    if "warning" in output.lower():
        return 1
    return 0


def parse_smoke_metrics(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "available": False,
            "checks_count": 0,
            "p95_ms": None,
            "avg_ms": None,
            "max_ms": None,
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    checks = payload.get("checks") if isinstance(payload, dict) else []
    latencies = [
        int(item.get("elapsedMs"))
        for item in checks
        if isinstance(item, dict) and isinstance(item.get("elapsedMs"), (int, float))
    ]
    if not latencies:
        return {
            "available": True,
            "checks_count": len(checks),
            "p95_ms": None,
            "avg_ms": None,
            "max_ms": None,
        }
    sorted_latencies = sorted(latencies)
    p95_index = min(
        len(sorted_latencies) - 1,
        max(0, int((len(sorted_latencies) - 1) * 0.95)),
    )
    return {
        "available": True,
        "checks_count": len(checks),
        "p95_ms": sorted_latencies[p95_index],
        "avg_ms": round(statistics.mean(sorted_latencies), 2),
        "max_ms": max(sorted_latencies),
    }


def parse_ingest_freshness(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"available": False, "freshness_lag_seconds": None}
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload if isinstance(payload, list) else []
    latest: datetime | None = None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        raw_value = entry.get("published_at")
        if not isinstance(raw_value, str):
            continue
        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
        except ValueError:
            continue
        if latest is None or parsed > latest:
            latest = parsed
    if latest is None:
        return {"available": True, "freshness_lag_seconds": None}
    lag_seconds = max(0, int((datetime.now(UTC) - latest).total_seconds()))
    return {
        "available": True,
        "latest_published_at": latest.isoformat(),
        "freshness_lag_seconds": lag_seconds,
    }


def collect_metrics(include_smoke: bool) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "commands": {},
    }
    active_module_paths = discover_active_module_paths()

    ruff_result = run_command([
        resolve_local_bin("ruff"),
        "check",
        "src",
        "tests",
        "--output-format",
        "json",
        "--exit-zero",
    ])
    metrics["commands"]["ruff"] = {
        "command": ruff_result.command,
        "return_code": ruff_result.return_code,
        **_command_diagnostics(ruff_result),
    }
    metrics["ruff_errors"] = parse_ruff_errors(ruff_result.stdout)
    ruff_active_breakdown = parse_ruff_errors_by_path(
        ruff_result.stdout,
        active_module_paths,
    )
    metrics["active_modules"] = list(active_module_paths)
    metrics["active_module_ruff_breakdown"] = ruff_active_breakdown
    metrics["active_module_ruff_errors"] = sum(ruff_active_breakdown.values())

    mypy_result = run_command([
        resolve_local_bin("mypy"),
        "src",
        "--ignore-missing-imports",
        "--no-error-summary",
    ])
    metrics["commands"]["mypy"] = {
        "command": mypy_result.command,
        "return_code": mypy_result.return_code,
        **_command_diagnostics(mypy_result),
    }
    mypy_combined = mypy_result.stdout + "\n" + mypy_result.stderr
    metrics["mypy_errors"] = parse_mypy_errors(mypy_combined)
    mypy_active_breakdown = parse_mypy_errors_by_path(
        mypy_combined,
        active_module_paths,
    )
    metrics["active_module_mypy_breakdown"] = mypy_active_breakdown
    metrics["active_module_mypy_errors"] = sum(mypy_active_breakdown.values())

    pytest_result = run_command([
        resolve_local_bin("pytest"),
        "tests/unit",
        "--cov=src/financial_news",
        "--cov-report=term",
        "-q",
    ])
    metrics["commands"]["pytest_unit_coverage"] = {
        "command": pytest_result.command,
        "return_code": pytest_result.return_code,
        **_command_diagnostics(pytest_result),
    }
    metrics["unit_tests_passed"] = pytest_result.return_code == 0
    metrics["coverage_unit_pct"] = parse_pytest_coverage_pct(pytest_result.stdout)

    tsc_result = run_command(["bunx", "tsc", "--noEmit"])
    metrics["commands"]["tsc"] = {
        "command": tsc_result.command,
        "return_code": tsc_result.return_code,
        **_command_diagnostics(tsc_result),
    }
    metrics["tsc_passed"] = tsc_result.return_code == 0

    eslint_result = run_command(["bun", "run", "lint"])
    metrics["commands"]["eslint"] = {
        "command": eslint_result.command,
        "return_code": eslint_result.return_code,
        **_command_diagnostics(eslint_result),
    }
    metrics["eslint_passed"] = eslint_result.return_code == 0
    metrics["eslint_warnings"] = parse_eslint_warnings(eslint_result.stdout + "\n" + eslint_result.stderr)

    smoke_passed: bool | None = None
    if include_smoke:
        smoke_result = run_command(["bun", "run", "smoke:frontend"])
        metrics["commands"]["smoke_frontend"] = {
            "command": smoke_result.command,
            "return_code": smoke_result.return_code,
            **_command_diagnostics(smoke_result),
        }
        smoke_passed = smoke_result.return_code == 0
    metrics["smoke_frontend_passed"] = smoke_passed
    smoke_metrics = parse_smoke_metrics(Path(".tmp/smoke/smoke-metrics.json"))
    metrics["smoke_checks_count"] = smoke_metrics["checks_count"]
    metrics["smoke_p95_ms"] = smoke_metrics["p95_ms"]
    metrics["smoke_avg_ms"] = smoke_metrics["avg_ms"]
    metrics["smoke_max_ms"] = smoke_metrics["max_ms"]

    freshness_metrics = parse_ingest_freshness(Path("data/ingested_articles.json"))
    metrics["ingest_freshness_lag_seconds"] = freshness_metrics.get(
        "freshness_lag_seconds"
    )

    return metrics


def render_markdown(metrics: dict[str, Any]) -> str:
    lines = [
        "# Quality Checkpoint",
        "",
        f"Generated at: `{metrics.get('generated_at')}`",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Ruff errors | {metrics.get('ruff_errors')} |",
        f"| Active-module Ruff errors | {metrics.get('active_module_ruff_errors')} |",
        f"| MyPy errors | {metrics.get('mypy_errors')} |",
        f"| Active-module MyPy errors | {metrics.get('active_module_mypy_errors')} |",
        f"| Unit coverage % | {metrics.get('coverage_unit_pct')} |",
        f"| Unit tests passed | {metrics.get('unit_tests_passed')} |",
        f"| TypeScript check passed | {metrics.get('tsc_passed')} |",
        f"| ESLint passed | {metrics.get('eslint_passed')} |",
        f"| ESLint warnings | {metrics.get('eslint_warnings')} |",
        f"| Smoke frontend passed | {metrics.get('smoke_frontend_passed')} |",
        f"| Smoke p95 latency (ms) | {metrics.get('smoke_p95_ms')} |",
        f"| Ingest freshness lag (s) | {metrics.get('ingest_freshness_lag_seconds')} |",
        "",
        "## Active Module Breakdown",
        "",
        "| Module | Ruff | MyPy |",
        "| --- | --- | --- |",
    ]

    active_modules = metrics.get("active_modules", [])
    ruff_breakdown = metrics.get("active_module_ruff_breakdown", {})
    mypy_breakdown = metrics.get("active_module_mypy_breakdown", {})
    lines.extend(
        [
            f"| `{module}` | {ruff_breakdown.get(module, 0)} | {mypy_breakdown.get(module, 0)} |"
            for module in active_modules
        ]
    )

    lines.extend(
        [
            "",
            "## Commands",
            "",
        ]
    )

    commands = metrics.get("commands", {})
    for name, payload in commands.items():
        lines.append(f"- `{name}`: `{payload.get('command')}` (rc={payload.get('return_code')})")
        stdout_tail = payload.get("stdout_tail")
        stderr_tail = payload.get("stderr_tail")
        if stdout_tail:
            lines.extend(
                [
                    "",
                    f"  stdout tail for `{name}`:",
                    "",
                    "  ```text",
                    *(f"  {line}" for line in str(stdout_tail).splitlines()),
                    "  ```",
                ]
            )
        if stderr_tail:
            lines.extend(
                [
                    "",
                    f"  stderr tail for `{name}`:",
                    "",
                    "  ```text",
                    *(f"  {line}" for line in str(stderr_tail).splitlines()),
                    "  ```",
                ]
            )

    return "\n".join(lines) + "\n"


def ratchet_against_baseline(
    *,
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> list[str]:
    failures: list[str] = []

    max_ruff = int(baseline.get("ruff_errors_max", 0))
    max_mypy = int(baseline.get("mypy_errors_max", 0))
    max_eslint_warnings = int(baseline.get("eslint_warnings_max", 0))
    min_coverage = baseline.get("coverage_unit_pct_min")
    active_ruff_max = baseline.get("active_module_ruff_errors_max")
    active_mypy_max = baseline.get("active_module_mypy_errors_max")

    if int(current.get("ruff_errors", 0)) > max_ruff:
        failures.append(
            f"Ruff regression: {current.get('ruff_errors')} > baseline max {max_ruff}"
        )

    if int(current.get("mypy_errors", 0)) > max_mypy:
        failures.append(
            f"MyPy regression: {current.get('mypy_errors')} > baseline max {max_mypy}"
        )

    if (
        active_ruff_max is not None
        and int(current.get("active_module_ruff_errors", 0)) > int(active_ruff_max)
    ):
        failures.append(
            "Active-module Ruff regression: "
            f"{current.get('active_module_ruff_errors')} > baseline max {active_ruff_max}"
        )

    if (
        active_mypy_max is not None
        and int(current.get("active_module_mypy_errors", 0)) > int(active_mypy_max)
    ):
        failures.append(
            "Active-module MyPy regression: "
            f"{current.get('active_module_mypy_errors')} > baseline max {active_mypy_max}"
        )

    if int(current.get("eslint_warnings", 0)) > max_eslint_warnings:
        failures.append(
            "ESLint warning regression: "
            f"{current.get('eslint_warnings')} > baseline max {max_eslint_warnings}"
        )

    current_coverage = current.get("coverage_unit_pct")
    if (
        min_coverage is not None
        and current_coverage is not None
        and float(current_coverage) < float(min_coverage)
    ):
        failures.append(
            "Coverage regression: "
            f"{current_coverage}% < baseline min {min_coverage}%"
        )

    max_smoke_p95 = baseline.get("max_smoke_p95_ms")
    current_smoke_p95 = current.get("smoke_p95_ms")
    if (
        baseline.get("require_smoke_latency", False)
        and max_smoke_p95 is not None
        and current_smoke_p95 is not None
        and int(current_smoke_p95) > int(max_smoke_p95)
    ):
        failures.append(
            f"Smoke latency regression: {current_smoke_p95}ms > baseline max {max_smoke_p95}ms"
        )

    max_freshness_lag = baseline.get("max_ingest_freshness_lag_seconds")
    current_freshness_lag = current.get("ingest_freshness_lag_seconds")
    if (
        baseline.get("require_ingest_freshness", False)
        and max_freshness_lag is not None
        and current_freshness_lag is not None
        and int(current_freshness_lag) > int(max_freshness_lag)
    ):
        failures.append(
            "Ingest freshness regression: "
            f"{current_freshness_lag}s > baseline max {max_freshness_lag}s"
        )

    required_bools = {
        "unit_tests_passed": "Unit tests",
        "tsc_passed": "TypeScript check",
        "eslint_passed": "ESLint",
    }
    for key, label in required_bools.items():
        if baseline.get(f"require_{key}", True) and not bool(current.get(key)):
            failures.append(f"{label} failed")
            command_name = "pytest_unit_coverage" if key == "unit_tests_passed" else None
            if command_name:
                command_payload = current.get("commands", {}).get(command_name, {})
                stdout_tail = command_payload.get("stdout_tail")
                stderr_tail = command_payload.get("stderr_tail")
                if stdout_tail:
                    failures.append(f"{label} stdout tail:\n{stdout_tail}")
                if stderr_tail:
                    failures.append(f"{label} stderr tail:\n{stderr_tail}")

    if baseline.get("require_smoke_frontend", False) and not bool(
        current.get("smoke_frontend_passed")
    ):
        failures.append("Frontend smoke check failed")

    return failures


def cmd_collect(args: argparse.Namespace) -> int:
    metrics = collect_metrics(include_smoke=bool(args.include_smoke))

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    if args.output_md:
        output_md = Path(args.output_md)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_markdown(metrics), encoding="utf-8")

    print(json.dumps(metrics, indent=2))
    return 0


def cmd_ratchet(args: argparse.Namespace) -> int:
    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    current = json.loads(Path(args.current).read_text(encoding="utf-8"))

    failures = ratchet_against_baseline(baseline=baseline, current=current)
    if failures:
        print("Quality ratchet failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Quality ratchet passed.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect and ratchet quality metrics")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect", help="Collect quality metrics")
    collect_parser.add_argument(
        "--output-json",
        default="output/quality/current.json",
        help="Path to write collected JSON metrics",
    )
    collect_parser.add_argument(
        "--output-md",
        default="output/quality/current.md",
        help="Path to write Markdown scorecard",
    )
    collect_parser.add_argument(
        "--include-smoke",
        action="store_true",
        help="Run frontend smoke API checks (bun run smoke:frontend)",
    )
    collect_parser.set_defaults(func=cmd_collect)

    ratchet_parser = subparsers.add_parser("ratchet", help="Check current metrics against baseline")
    ratchet_parser.add_argument(
        "--baseline",
        default="config/quality-baseline.json",
        help="Path to baseline JSON",
    )
    ratchet_parser.add_argument(
        "--current",
        default="output/quality/current.json",
        help="Path to current metrics JSON",
    )
    ratchet_parser.set_defaults(func=cmd_ratchet)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
