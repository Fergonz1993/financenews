#!/usr/bin/env python3
"""Unit tests for the continuous ingestion runner."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from financial_news.services.continuous_runner import (
    ContinuousIngestRunner,
    _classify_error,
    _env_bool,
    _env_int,
    get_runner,
)


class TestEnvHelpers:
    def test_env_bool_true_values(self) -> None:
        for value in ["true", "1", "yes", "on"]:
            with patch.dict("os.environ", {"TEST_VAR": value}):
                assert _env_bool("TEST_VAR") is True

    def test_env_bool_false_values(self) -> None:
        for value in ["false", "0", "no"]:
            with patch.dict("os.environ", {"TEST_VAR": value}):
                assert _env_bool("TEST_VAR") is False

    def test_env_bool_default(self) -> None:
        assert _env_bool("NONEXISTENT_VAR") is False
        assert _env_bool("NONEXISTENT_VAR", default=True) is True

    def test_env_int_valid(self) -> None:
        with patch.dict("os.environ", {"TEST_INT": "42"}):
            assert _env_int("TEST_INT", 10) == 42

    def test_env_int_invalid_default(self) -> None:
        with patch.dict("os.environ", {"TEST_INT": "not-a-number"}):
            assert _env_int("TEST_INT", 50) == 50

    def test_env_int_clamps_to_one(self) -> None:
        with patch.dict("os.environ", {"TEST_INT": "0"}):
            assert _env_int("TEST_INT", 10) == 1

    @pytest.mark.parametrize(
        ("raw_error", "expected"),
        [
            ("timeout while reading", "timeout"),
            ("HTTP 429", "rate_limited"),
            ("connection refused", "connection_error"),
            ("auth failed", "authentication_error"),
            ("validation failed", "validation_error"),
            ("other", "unknown_error"),
        ],
    )
    def test_classify_error(self, raw_error: str, expected: str) -> None:
        assert _classify_error(raw_error) == expected


class TestContinuousIngestRunner:
    @staticmethod
    def _runner_like() -> ContinuousIngestRunner:
        runner = ContinuousIngestRunner.__new__(ContinuousIngestRunner)
        runner._running = True
        runner._task = None
        runner._cycle_count = 3
        runner._last_cycle_at = datetime(2026, 2, 25, tzinfo=UTC)
        runner._last_cycle_articles = 12
        runner._total_articles_ingested = 42
        runner._errors = [{"error": f"err-{idx}"} for idx in range(12)]
        runner._connector_status = {
            "gdelt": {
                "state": "ready",
                "last_fetch_at": datetime(2026, 2, 25, 12, 0, tzinfo=UTC).isoformat(),
                "last_articles_fetched": 8,
                "last_articles_stored": 5,
            }
        }
        runner._connector_events = [
            {
                "at": datetime(2026, 2, 25, 12, 0, tzinfo=UTC),
                "connector": "gdelt",
                "ok": True,
                "fetched": 8,
                "stored": 5,
                "latency_ms": 120,
                "error_code": None,
            }
        ]
        runner.enabled = True
        runner.interval_seconds = 300
        runner._connector_defaults = {
            "gdelt": True,
            "sec_edgar": True,
            "newsdata": False,
            "reddit": False,
        }
        runner._CONNECTOR_FACTORIES = {
            "gdelt": ("GDELT Project", object),
            "sec_edgar": ("SEC EDGAR", object),
            "newsdata": ("Newsdata.io", object),
            "reddit": ("Reddit Finance", object),
        }
        runner._configured_connector_enabled = {
            "gdelt": True,
            "sec_edgar": True,
            "newsdata": False,
            "reddit": False,
        }
        runner._connector_runtime_overrides = {}
        runner._stock_correlator_enabled = False
        runner._stock_correlator = None
        return runner

    def test_get_status_includes_connectors(self) -> None:
        runner = self._runner_like()
        status = runner.get_status()

        assert status["running"] is True
        assert status["cycle_count"] == 3
        assert status["total_articles_ingested"] == 42
        assert status["connectors"]["gdelt"]["enabled"] is True
        assert status["connectors"]["gdelt"]["state"] == "ready"
        assert status["connectors"]["newsdata"]["enabled"] is False
        assert status["connectors"]["newsdata"]["state"] == "disabled"
        assert len(status["recent_errors"]) == 8

    def test_set_connector_enabled_and_reset(self) -> None:
        runner = self._runner_like()

        toggled = runner.set_connector_enabled("gdelt", False)
        assert toggled["effective_enabled"] is False
        status = runner.get_status()
        assert status["connectors"]["gdelt"]["enabled"] is False
        assert status["connectors"]["gdelt"]["runtime_override"] is False

        reset = runner.clear_connector_override("gdelt")
        assert reset["runtime_override"] is None
        status_after_reset = runner.get_status()
        assert status_after_reset["connectors"]["gdelt"]["enabled"] is True
        assert status_after_reset["connectors"]["gdelt"]["runtime_override"] is None

    def test_set_connector_enabled_rejects_unknown(self) -> None:
        runner = self._runner_like()
        with pytest.raises(KeyError):
            runner.set_connector_enabled("unknown", True)

    def test_ensure_event_store_migrates_legacy_list(self) -> None:
        runner = self._runner_like()
        runner._connector_events = [
            {
                "connector": "gdelt",
                "ok": True,
                "fetched": 4,
                "stored": 2,
                "latency_ms": 99,
                "error_code": None,
                "at": datetime(2026, 2, 25, 12, 0, tzinfo=UTC),
            }
        ]

        migrated = runner._ensure_event_store()
        assert "gdelt" in migrated
        assert migrated["gdelt"][0]["state"] == "ready"
        assert migrated["gdelt"][0]["stored"] == 2
        assert migrated["gdelt"][0]["success"] is True

    def test_build_connector_slo_uses_recent_events_and_freshness(self) -> None:
        runner = self._runner_like()
        now = datetime.now(UTC)
        runner._connector_events = {
            "gdelt": [
                {
                    "time": (now - timedelta(hours=1)).isoformat(),
                    "state": "ready",
                    "fetched": 5,
                    "validated": 5,
                    "rejected": 0,
                    "stored": 3,
                    "latency_ms": 100,
                    "success": True,
                    "error_code": None,
                },
                {
                    "time": (now - timedelta(hours=2)).isoformat(),
                    "state": "error",
                    "fetched": 0,
                    "validated": 0,
                    "rejected": 0,
                    "stored": 0,
                    "latency_ms": 200,
                    "success": False,
                    "error_code": "timeout",
                },
            ]
        }
        runner._connector_status["gdelt"] = {
            "last_success_at": (now.replace(minute=0, second=0, microsecond=0)).isoformat()
        }

        slo = runner._build_connector_slo("gdelt")
        assert slo["events"] == 2
        assert slo["success_rate_pct"] == 50.0
        assert slo["articles_stored"] == 3
        assert slo["avg_latency_ms"] == 150.0
        assert slo["freshness_lag_seconds"] is None or isinstance(
            slo["freshness_lag_seconds"], int
        )


class TestGetRunner:
    def test_singleton(self) -> None:
        import financial_news.services.continuous_runner as mod

        mod._runner = None
        runner1 = get_runner(session_factory=SimpleNamespace())
        runner2 = get_runner(session_factory=SimpleNamespace())
        assert runner1 is runner2
        mod._runner = None
