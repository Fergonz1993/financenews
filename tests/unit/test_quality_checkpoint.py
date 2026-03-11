from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_quality_checkpoint():
    module_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "quality_checkpoint.py"
    )
    spec = importlib.util.spec_from_file_location("quality_checkpoint", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_discover_active_module_paths_returns_relevant_changed_modules(monkeypatch) -> None:
    quality_checkpoint = _load_quality_checkpoint()

    changed_test_file = "tests/unit/test_api_route_regression.py"

    def fake_git_stdout_lines(command: list[str]) -> list[str]:
        if command[:3] == ["git", "diff-tree", "--no-commit-id"]:
            return [changed_test_file]
        return []

    monkeypatch.setattr(quality_checkpoint, "_git_stdout_lines", fake_git_stdout_lines)
    monkeypatch.setattr(quality_checkpoint, "_git_has_head_parent", lambda: False)

    assert quality_checkpoint.discover_active_module_paths() == (changed_test_file,)


def test_discover_active_module_paths_returns_empty_tuple_for_non_module_commit(
    monkeypatch,
) -> None:
    quality_checkpoint = _load_quality_checkpoint()

    def fake_git_stdout_lines(command: list[str]) -> list[str]:
        if command[:3] == ["git", "diff-tree", "--no-commit-id"]:
            return ["scripts/quality_checkpoint.py"]
        return []

    monkeypatch.setattr(quality_checkpoint, "_git_stdout_lines", fake_git_stdout_lines)
    monkeypatch.setattr(quality_checkpoint, "_git_has_head_parent", lambda: False)

    assert quality_checkpoint.discover_active_module_paths() == ()


def test_discover_active_module_paths_uses_legacy_fallback_without_git_signal(
    monkeypatch,
) -> None:
    quality_checkpoint = _load_quality_checkpoint()

    monkeypatch.setattr(quality_checkpoint, "_git_stdout_lines", lambda _command: [])
    monkeypatch.setattr(quality_checkpoint, "_git_has_head_parent", lambda: False)

    assert (
        quality_checkpoint.discover_active_module_paths()
        == quality_checkpoint.LEGACY_ACTIVE_MODULE_PATHS
    )
