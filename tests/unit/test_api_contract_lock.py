#!/usr/bin/env python3
"""API contract lock tests — ensures the OpenAPI schema stays stable.

These tests prevent accidental breaking changes to the public API surface.
If a test fails, it means the API contract changed — update the snapshot
deliberately if the change is intentional.
"""

from __future__ import annotations

from financial_news.api.main import app

# ---------------------------------------------------------------------------
# Snapshot of every public API path + method as of 2026-03-06.
# If you add, rename, or remove an endpoint, update this set.
# ---------------------------------------------------------------------------
EXPECTED_PATHS: set[tuple[str, str]] = {
    ("GET", "/"),
    ("GET", "/health"),
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
    # --- Articles ---
    ("GET", "/api/articles"),
    ("GET", "/api/articles/count"),
    ("GET", "/api/articles/{article_id}"),
    # --- Analytics ---
    ("GET", "/api/analytics"),
    ("POST", "/api/analyze/sentiment"),
    # --- Sources ---
    ("GET", "/api/sources"),
    ("POST", "/api/sources"),
    ("POST", "/api/sources/validate"),
    ("DELETE", "/api/sources/{source_identifier}"),
    ("GET", "/api/sources/{source_identifier}/health"),
    # --- Topics ---
    ("GET", "/api/topics"),
    # --- Ingestion ---
    ("POST", "/api/ingest"),
    ("GET", "/api/ingest/status"),
    ("POST", "/api/ingest/trigger"),
    ("GET", "/api/ingest/telemetry"),
    ("GET", "/api/ingest/runs/{run_id}"),
    ("GET", "/api/ingest/continuous/status"),
    ("POST", "/api/ingest/continuous/trigger"),
    ("POST", "/api/ingest/continuous/connectors/{connector_name}"),
    # --- Admin ---
    ("POST", "/api/admin/ingest/run"),
    ("GET", "/api/admin/sources/{source_identifier}/health"),
    ("GET", "/api/ingestion/health"),
    # --- User settings/alerts ---
    ("GET", "/api/user/settings"),
    ("PUT", "/api/user/settings"),
    ("POST", "/api/user/settings"),
    ("GET", "/api/user/alerts"),
    ("PUT", "/api/user/alerts"),
    ("POST", "/api/user/alerts"),
    # --- Saved articles ---
    ("GET", "/api/users/{user_id}/saved-articles"),
    ("POST", "/api/users/{user_id}/saved-articles/{article_id}"),
    ("DELETE", "/api/users/{user_id}/saved-articles/{article_id}"),
    ("GET", "/api/users/{user_id}/saved-articles/{article_id}/status"),
    # --- Notifications ---
    ("POST", "/api/notifications/send"),
}


def _get_actual_paths() -> set[tuple[str, str]]:
    schema = app.openapi()
    paths: set[tuple[str, str]] = set()
    for path, methods in schema.get("paths", {}).items():
        for method in methods:
            paths.add((method.upper(), path))
    return paths


class TestApiContractLock:
    """Ensures no endpoints are accidentally added, removed, or renamed."""

    def test_no_missing_endpoints(self) -> None:
        actual = _get_actual_paths()
        missing = EXPECTED_PATHS - actual
        assert not missing, f"Missing API endpoints: {missing}"

    def test_no_unexpected_endpoints(self) -> None:
        actual = _get_actual_paths()
        unexpected = actual - EXPECTED_PATHS
        assert not unexpected, (
            f"Unexpected new API endpoints detected: {unexpected}\n"
            "If intentional, add them to EXPECTED_PATHS in this test file."
        )

    def test_endpoint_count_stable(self) -> None:
        actual = _get_actual_paths()
        assert len(actual) == len(EXPECTED_PATHS), (
            f"Endpoint count changed: expected {len(EXPECTED_PATHS)}, got {len(actual)}"
        )


class TestApiResponseSchemas:
    """Validates that key endpoints have response schemas defined."""

    def test_articles_endpoint_has_response_schema(self) -> None:
        schema = app.openapi()
        articles_path = schema["paths"].get("/api/articles", {})
        get_op = articles_path.get("get", {})
        assert "responses" in get_op
        assert "200" in get_op["responses"]

    def test_analytics_endpoint_has_response_schema(self) -> None:
        schema = app.openapi()
        analytics_path = schema["paths"].get("/api/analytics", {})
        get_op = analytics_path.get("get", {})
        assert "responses" in get_op
        assert "200" in get_op["responses"]

    def test_ingest_status_has_response_schema(self) -> None:
        schema = app.openapi()
        status_path = schema["paths"].get("/api/ingest/status", {})
        get_op = status_path.get("get", {})
        assert "responses" in get_op
        assert "200" in get_op["responses"]

    def test_sources_endpoint_has_response_schema(self) -> None:
        schema = app.openapi()
        sources_path = schema["paths"].get("/api/sources", {})
        get_op = sources_path.get("get", {})
        assert "responses" in get_op
        assert "200" in get_op["responses"]

    def test_health_endpoint_has_response_schema(self) -> None:
        schema = app.openapi()
        health_path = schema["paths"].get("/health", {})
        get_op = health_path.get("get", {})
        assert "responses" in get_op
        assert "200" in get_op["responses"]

    def test_readiness_endpoint_has_response_schema(self) -> None:
        schema = app.openapi()
        readiness_path = schema["paths"].get("/health/ready", {})
        get_op = readiness_path.get("get", {})
        assert "responses" in get_op
        assert "200" in get_op["responses"]


class TestApiSchemaMetadata:
    """Validates the OpenAPI schema has proper metadata."""

    def test_schema_has_title(self) -> None:
        schema = app.openapi()
        assert schema.get("info", {}).get("title") == "Financial News API"

    def test_schema_has_version(self) -> None:
        schema = app.openapi()
        assert schema.get("info", {}).get("version")

    def test_schema_has_description(self) -> None:
        schema = app.openapi()
        assert schema.get("info", {}).get("description")

    def test_article_response_model_exists(self) -> None:
        schema = app.openapi()
        components = schema.get("components", {}).get("schemas", {})
        assert "ArticleResponse" in components
        article_schema = components["ArticleResponse"]
        assert "id" in article_schema.get("properties", {})
        assert "title" in article_schema.get("properties", {})
        assert "url" in article_schema.get("properties", {})
        assert "source" in article_schema.get("properties", {})
