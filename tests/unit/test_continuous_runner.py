#!/usr/bin/env python3
"""Unit tests for the continuous ingestion runner."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from financial_news.services.continuous_runner import (
    ContinuousIngestRunner,
    _env_bool,
    _env_int,
    get_runner,
)


class TestEnvHelpers:
    def test_env_bool_true_values(self):
        with patch.dict("os.environ", {"TEST_VAR": "true"}):
            assert _env_bool("TEST_VAR") is True
        with patch.dict("os.environ", {"TEST_VAR": "1"}):
            assert _env_bool("TEST_VAR") is True
        with patch.dict("os.environ", {"TEST_VAR": "yes"}):
            assert _env_bool("TEST_VAR") is True
        with patch.dict("os.environ", {"TEST_VAR": "on"}):
            assert _env_bool("TEST_VAR") is True

    def test_env_bool_false_values(self):
        with patch.dict("os.environ", {"TEST_VAR": "false"}):
            assert _env_bool("TEST_VAR") is False
        with patch.dict("os.environ", {"TEST_VAR": "0"}):
            assert _env_bool("TEST_VAR") is False
        with patch.dict("os.environ", {"TEST_VAR": "no"}):
            assert _env_bool("TEST_VAR") is False

    def test_env_bool_default(self):
        assert _env_bool("NONEXISTENT_VAR") is False
        assert _env_bool("NONEXISTENT_VAR", default=True) is True

    def test_env_int_valid(self):
        with patch.dict("os.environ", {"TEST_INT": "42"}):
            assert _env_int("TEST_INT", 10) == 42

    def test_env_int_default(self):
        assert _env_int("NONEXISTENT_INT", 99) == 99

    def test_env_int_invalid(self):
        with patch.dict("os.environ", {"TEST_INT": "not_a_number"}):
            assert _env_int("TEST_INT", 50) == 50

    def test_env_int_clamps_to_one(self):
        with patch.dict("os.environ", {"TEST_INT": "0"}):
            assert _env_int("TEST_INT", 10) == 1
        with patch.dict("os.environ", {"TEST_INT": "-5"}):
            assert _env_int("TEST_INT", 10) == 1


class TestContinuousIngestRunner:
    def test_initial_state(self):
        with patch.dict("os.environ", {
            "CONTINUOUS_INGEST_ENABLED": "true",
            "CONTINUOUS_INGEST_INTERVAL_SECONDS": "120",
        }):
            runner = ContinuousIngestRunner.__new__(ContinuousIngestRunner)
            runner._running = False
            runner._task = None
            runner._cycle_count = 0
            runner._last_cycle_at = None
            runner._last_cycle_articles = 0
            runner._total_articles_ingested = 0
            runner._errors = []
            runner._connector_status = {}
            runner.enabled = True
            runner.interval_seconds = 120
            runner.gdelt_enabled = True
            runner.sec_edgar_enabled = True
            runner.newsdata_enabled = True

            assert runner.is_running is False
            status = runner.get_status()
            assert status["enabled"] is True
            assert status["running"] is False
            assert status["cycle_count"] == 0
            assert status["interval_seconds"] == 120

    def test_get_status_includes_connectors(self):
        runner = ContinuousIngestRunner.__new__(ContinuousIngestRunner)
        runner._running = True
        runner._task = None
        runner._cycle_count = 3
        runner._last_cycle_at = datetime(2026, 2, 25, tzinfo=timezone.utc)
        runner._last_cycle_articles = 12
        runner._total_articles_ingested = 42
        runner._errors = []
        runner._connector_status = {
            "gdelt": {"status": "ok", "last_articles_stored": 5},
        }
        runner.enabled = True
        runner.interval_seconds = 300
        runner.gdelt_enabled = True
        runner.sec_edgar_enabled = True
        runner.newsdata_enabled = False

        status = runner.get_status()
        assert status["running"] is True
        assert status["cycle_count"] == 3
        assert status["total_articles_ingested"] == 42
        assert "connectors" in status
        assert status["connectors"]["gdelt"]["enabled"] is True
        assert status["connectors"]["gdelt"]["status"] == "ok"
        assert status["connectors"]["newsdata"]["enabled"] is False

    def test_get_status_next_cycle_calculation(self):
        runner = ContinuousIngestRunner.__new__(ContinuousIngestRunner)
        runner._running = True
        runner._task = None
        runner._cycle_count = 1
        runner._last_cycle_at = datetime(2026, 2, 25, 12, 0, 0, tzinfo=timezone.utc)
        runner._last_cycle_articles = 0
        runner._total_articles_ingested = 0
        runner._errors = []
        runner._connector_status = {}
        runner.enabled = True
        runner.interval_seconds = 300
        runner.gdelt_enabled = True
        runner.sec_edgar_enabled = True
        runner.newsdata_enabled = True

        status = runner.get_status()
        assert status["next_cycle_at"] is not None
        # next_cycle_at should be 5 min after last_cycle_at
        assert "2026-02-25T12:05:00" in status["next_cycle_at"]

    def test_errors_capped(self):
        runner = ContinuousIngestRunner.__new__(ContinuousIngestRunner)
        runner._running = False
        runner._task = None
        runner._cycle_count = 0
        runner._last_cycle_at = None
        runner._last_cycle_articles = 0
        runner._total_articles_ingested = 0
        runner._errors = [{"error": f"err-{i}"} for i in range(25)]
        runner._connector_status = {}
        runner.enabled = True
        runner.interval_seconds = 300
        runner.gdelt_enabled = True
        runner.sec_edgar_enabled = True
        runner.newsdata_enabled = True

        status = runner.get_status()
        assert len(status["recent_errors"]) == 5  # Only last 5


class TestGetRunner:
    def test_singleton(self):
        import financial_news.services.continuous_runner as mod
        mod._runner = None  # Reset singleton
        runner1 = get_runner()
        runner2 = get_runner()
        assert runner1 is runner2
        mod._runner = None  # Cleanup
