"""Route-level regression tests for the refactored FastAPI app."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import financial_news.api.main as api_main
from financial_news.api.routes import system as system_routes


def _patch_lifespan(monkeypatch) -> None:
    monkeypatch.setattr(api_main, "generate_demo_alerts", AsyncMock(return_value=None))
    monkeypatch.setattr(api_main, "run_startup_ingest", AsyncMock(return_value=None))
    monkeypatch.setattr(api_main.continuous_runner, "start", AsyncMock(return_value=None))
    monkeypatch.setattr(api_main.continuous_runner, "stop", AsyncMock(return_value=None))


def test_health_ready_reports_degraded_when_db_check_fails(monkeypatch) -> None:
    _patch_lifespan(monkeypatch)
    monkeypatch.setattr(
        system_routes,
        "get_db_health_check",
        lambda: AsyncMock(return_value=False),
    )

    with TestClient(api_main.app) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json()["status"] == "live"
    assert ready.status_code == 503
    assert ready.json()["status"] == "degraded"
    assert ready.json()["checks"]["database"] is False


def test_ingest_trigger_error_envelope_includes_request_id(monkeypatch) -> None:
    _patch_lifespan(monkeypatch)
    monkeypatch.setattr(api_main, "ADMIN_API_KEY", "secret-key")

    with TestClient(api_main.app) as client:
        response = client.post("/api/ingest/trigger", headers={"X-Request-Id": "req-401"})

    assert response.status_code == 401
    payload = response.json()
    assert payload["error"]["message"] == "Missing admin credentials"
    assert payload["error"]["request_id"] == "req-401"


def test_ingest_trigger_success_includes_request_id(monkeypatch) -> None:
    _patch_lifespan(monkeypatch)
    monkeypatch.setattr(api_main, "ADMIN_API_KEY", "secret-key")
    monkeypatch.setattr(
        api_main.ingester,
        "start_async_ingest",
        AsyncMock(return_value="run-123"),
    )

    with TestClient(api_main.app) as client:
        response = client.post(
            "/api/ingest/trigger",
            headers={
                "X-Admin-Api-Key": "secret-key",
                "X-Request-Id": "req-ok",
            },
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["run_id"] == "run-123"
    assert payload["request_id"] == "req-ok"


def test_user_settings_route_uses_schema_and_repo_contract(monkeypatch) -> None:
    _patch_lifespan(monkeypatch)
    monkeypatch.setattr(api_main, "initialize_schema", AsyncMock(return_value=None))
    monkeypatch.setattr(
        api_main.user_settings_repo,
        "get",
        AsyncMock(
            return_value={
                "darkMode": False,
                "autoRefresh": True,
                "refreshInterval": 15,
                "defaultFilters": {"sources": ["Reuters"], "topics": [], "sentiment": None},
                "emailAlerts": {"enabled": True, "frequency": "daily", "keywords": ["fed"]},
                "visualization": {"chartType": "line", "colorScheme": "default"},
            }
        ),
    )

    with TestClient(api_main.app) as client:
        response = client.get("/api/user/settings", params={"user_id": "alice"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["darkMode"] is False
    assert payload["autoRefresh"] is True
    assert payload["defaultFilters"]["sources"] == ["Reuters"]


def test_websocket_connection_established_envelope_contains_request_id(monkeypatch) -> None:
    _patch_lifespan(monkeypatch)

    with (
        TestClient(api_main.app) as client,
        client.websocket_connect("/ws?user_id=alice") as websocket,
    ):
        message = websocket.receive_json()

    assert message["type"] == "connection_established"
    assert message["payload"]["user_id"] == "alice"
    assert message["request_id"]
