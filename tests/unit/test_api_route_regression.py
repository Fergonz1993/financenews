"""Route-level regression tests for the refactored FastAPI app."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import financial_news.api.main as api_main
from financial_news.api.routes import articles as article_routes
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


def test_articles_route_uses_settings_for_relevance_ranking(monkeypatch) -> None:
    _patch_lifespan(monkeypatch)
    monkeypatch.setattr(
        api_main.app.state.container.settings.ingest,
        "feed_ranking_v2_enabled",
        True,
    )
    monkeypatch.setattr(
        api_main.app.state.container.settings.ingest,
        "feed_ranking_v2_candidate_multiplier",
        7,
    )
    monkeypatch.setattr(
        api_main.app.state.container.settings.ingest,
        "feed_ranking_v2_max_candidates",
        250,
    )
    monkeypatch.setattr(
        api_main.app.state.container.settings.ingest,
        "feed_ranking_v2_dedup_enabled",
        False,
    )
    ranked_loader = AsyncMock(
        return_value=[
            {
                "id": "ranked-http-1",
                "title": "Ranked HTTP article",
                "url": "https://example.com/ranked-http-1",
                "source": "Rank Source",
                "published_at": "2026-02-28T00:00:00+00:00",
                "summarized_headline": "Ranked summary",
                "summary_bullets": ["One"],
                "sentiment": "neutral",
                "sentiment_score": 0.4,
                "market_impact_score": 0.8,
                "key_entities": ["AAPL"],
                "topics": ["Markets"],
            }
        ]
    )
    fallback_loader = AsyncMock(return_value=[])
    monkeypatch.setattr(article_routes, "_load_ranked_articles_v2", ranked_loader)
    monkeypatch.setattr(article_routes, "_load_articles_from_db", fallback_loader)

    with TestClient(api_main.app) as client:
        response = client.get("/api/articles", params={"sort_by": "relevance", "limit": 1})

    assert response.status_code == 200
    payload = response.json()
    assert [row["id"] for row in payload] == ["ranked-http-1"]
    ranked_loader.assert_awaited_once()
    fallback_loader.assert_not_awaited()


def test_ingest_status_route_reports_configured_refresh_interval(monkeypatch) -> None:
    _patch_lifespan(monkeypatch)
    monkeypatch.setattr(
        api_main.app.state.container.settings.ingest,
        "auto_ingest_interval_seconds",
        900,
    )
    fake_run = type(
        "FakeRun",
        (),
        {"as_dict": lambda self: {"run_id": "run-http", "status": "completed"}},
    )()
    monkeypatch.setattr(api_main.ingester, "get_last_run", AsyncMock(return_value=fake_run))
    monkeypatch.setattr(api_main.ingester, "count_articles", AsyncMock(return_value=42))
    monkeypatch.setattr(api_main.ingester, "get_source_health", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        api_main.continuous_runner,
        "get_status",
        lambda: {"running": True, "interval_seconds": 300, "connectors": {}},
    )

    with TestClient(api_main.app) as client:
        response = client.get("/api/ingest/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scheduled_refresh_seconds"] == 900
    assert payload["stored_article_count"] == 42


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
