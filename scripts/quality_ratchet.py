#!/usr/bin/env python3
"""Compatibility wrapper for legacy quality ratchet command."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    command = [
        sys.executable,
        "scripts/quality_checkpoint.py",
        "ratchet",
        "--baseline",
        "config/quality-baseline.json",
        "--current",
        "output/quality/current.json",
    ]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
