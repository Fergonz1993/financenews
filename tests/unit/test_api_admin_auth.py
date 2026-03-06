"""Unit tests for admin auth protection on mutating API endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import financial_news.api.main as api_main


def test_ingest_trigger_requires_admin_key(monkeypatch) -> None:
    monkeypatch.setattr(api_main, "ADMIN_API_KEY", "secret-key")
    monkeypatch.setattr(api_main, "generate_demo_alerts", AsyncMock(return_value=None))
    monkeypatch.setattr(api_main, "run_startup_ingest", AsyncMock(return_value=None))
    monkeypatch.setattr(api_main.continuous_runner, "start", AsyncMock(return_value=None))
    monkeypatch.setattr(api_main.continuous_runner, "stop", AsyncMock(return_value=None))
    monkeypatch.setattr(api_main.ingester, "start_async_ingest", AsyncMock(return_value="run-123"))

    with TestClient(api_main.app) as client:
        no_key = client.post("/api/ingest/trigger")
        wrong_key = client.post("/api/ingest/trigger", headers={"X-Admin-Api-Key": "wrong"})
        ok = client.post("/api/ingest/trigger", headers={"X-Admin-Api-Key": "secret-key"})

    assert no_key.status_code == 401
    assert wrong_key.status_code == 403
    assert ok.status_code == 202
    assert ok.json().get("run_id") == "run-123"


def test_connector_toggle_endpoint_is_admin_protected(monkeypatch) -> None:
    monkeypatch.setattr(api_main, "ADMIN_API_KEY", "secret-key")
    monkeypatch.setattr(api_main, "generate_demo_alerts", AsyncMock(return_value=None))
    monkeypatch.setattr(api_main, "run_startup_ingest", AsyncMock(return_value=None))
    monkeypatch.setattr(api_main.continuous_runner, "start", AsyncMock(return_value=None))
    monkeypatch.setattr(api_main.continuous_runner, "stop", AsyncMock(return_value=None))
    monkeypatch.setattr(
        api_main.continuous_runner,
        "set_connector_enabled",
        lambda connector, enabled, actor="system": {
            "connector": connector,
            "enabled": enabled,
            "actor": actor,
        },
    )

    with TestClient(api_main.app) as client:
        unauthorized = client.post(
            "/api/ingest/continuous/connectors/newsdata",
            json={"enabled": True},
        )
        authorized = client.post(
            "/api/ingest/continuous/connectors/newsdata",
            json={"enabled": True},
            headers={"X-Admin-Api-Key": "secret-key", "X-Admin-User": "tester"},
        )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    payload = authorized.json()
    assert payload["toggle"]["connector"] == "newsdata"
    assert payload["toggle"]["enabled"] is True
