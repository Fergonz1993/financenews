#!/usr/bin/env python3
"""Compatibility wrapper for historical scripts/quality path."""

from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate baseline metrics")
    parser.add_argument("--json-out", default="output/quality/current.json")
    parser.add_argument("--markdown-out", default="output/quality/current.md")
    args = parser.parse_args()

    command = [
        sys.executable,
        "scripts/quality_checkpoint.py",
        "collect",
        "--output-json",
        args.json_out,
        "--output-md",
        args.markdown_out,
    ]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
