#!/usr/bin/env python3
"""Compatibility wrapper for legacy quality baseline command."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    command = [
        sys.executable,
        "scripts/quality_checkpoint.py",
        "collect",
        "--output-json",
        "output/quality/current.json",
        "--output-md",
        "output/quality/current.md",
    ]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
