#!/usr/bin/env python3
"""Admin security hardening tests — rate limiting, audit trail, input validation.

Covers TASK.md item 5: Security admin (auth/rbac/rate-limit/audit).
"""

from __future__ import annotations

import time

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from financial_news.api import main as api_main


async def _empty_receive() -> dict[str, object]:
    return {"type": "http.request", "body": b"", "more_body": False}


def _build_request(
    headers: dict[str, str] | None = None,
    client_host: str = "127.0.0.1",
) -> Request:
    headers = headers or {}
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/ingest/trigger",
        "headers": raw_headers,
        "client": (client_host, 12345),
    }
    return Request(scope, _empty_receive)


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------
class TestAdminRateLimit:
    def setup_method(self) -> None:
        api_main._ADMIN_REQUEST_HISTORY.clear()

    def test_allows_requests_under_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(api_main, "ADMIN_RATE_LIMIT_PER_MINUTE", 5)
        req = _build_request({"x-admin-user": "tester"})
        # Should not raise for the first 5 requests
        for _ in range(5):
            api_main._enforce_admin_rate_limit(req)

    def test_blocks_when_limit_exceeded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(api_main, "ADMIN_RATE_LIMIT_PER_MINUTE", 3)
        req = _build_request({"x-admin-user": "tester"})
        for _ in range(3):
            api_main._enforce_admin_rate_limit(req)
        with pytest.raises(HTTPException) as exc_info:
            api_main._enforce_admin_rate_limit(req)
        assert exc_info.value.status_code == 429
        assert "rate limit" in str(exc_info.value.detail).lower()

    def test_disabled_when_limit_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(api_main, "ADMIN_RATE_LIMIT_PER_MINUTE", 0)
        req = _build_request({"x-admin-user": "tester"})
        # Should never raise, even after many calls
        for _ in range(100):
            api_main._enforce_admin_rate_limit(req)

    def test_rate_limit_per_actor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(api_main, "ADMIN_RATE_LIMIT_PER_MINUTE", 2)
        req_a = _build_request({"x-admin-user": "alice"})
        req_b = _build_request({"x-admin-user": "bob"})
        # Alice uses 2 slots
        api_main._enforce_admin_rate_limit(req_a)
        api_main._enforce_admin_rate_limit(req_a)
        # Alice is blocked
        with pytest.raises(HTTPException):
            api_main._enforce_admin_rate_limit(req_a)
        # Bob can still make requests
        api_main._enforce_admin_rate_limit(req_b)


# ---------------------------------------------------------------------------
# Actor Resolution
# ---------------------------------------------------------------------------
class TestRequestActorFromHeaders:
    def test_uses_admin_user_header(self) -> None:
        req = _build_request({"x-admin-user": "deploy-bot"})
        assert api_main._request_actor_from_headers(req) == "deploy-bot"

    def test_uses_admin_actor_header(self) -> None:
        req = _build_request({"x-admin-actor": "ci-system"})
        assert api_main._request_actor_from_headers(req) == "ci-system"

    def test_falls_back_to_ip(self) -> None:
        req = _build_request(client_host="10.0.0.5")
        result = api_main._request_actor_from_headers(req)
        assert "10.0.0.5" in result

    def test_untrusted_returns_anonymous(self) -> None:
        req = _build_request()
        result = api_main._request_actor_from_headers(req, trusted=False)
        assert result == "anonymous"


# ---------------------------------------------------------------------------
# Admin Auth — Role-Based Access
# ---------------------------------------------------------------------------
class TestAdminRBAC:
    def setup_method(self) -> None:
        api_main._ADMIN_REQUEST_HISTORY.clear()

    def test_valid_key_valid_role_returns_actor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(api_main, "ADMIN_API_KEY", "secret-key")
        monkeypatch.setattr(api_main, "ADMIN_ALLOWED_ROLES", {"admin", "ops"})
        req = _build_request({
            "x-admin-key": "secret-key",
            "x-admin-role": "ops",
            "x-admin-user": "deploy-bot",
        })
        actor = api_main._require_admin_access(req)
        assert actor == "deploy-bot"

    def test_valid_key_wrong_role_rejects(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(api_main, "ADMIN_API_KEY", "secret-key")
        monkeypatch.setattr(api_main, "ADMIN_ALLOWED_ROLES", {"admin"})
        req = _build_request({
            "x-admin-key": "secret-key",
            "x-admin-role": "viewer",
        })
        with pytest.raises(HTTPException) as exc_info:
            api_main._require_admin_access(req)
        assert exc_info.value.status_code == 403

    def test_missing_key_rejects(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(api_main, "ADMIN_API_KEY", "secret-key")
        req = _build_request()
        with pytest.raises(HTTPException) as exc_info:
            api_main._require_admin_access(req)
        assert exc_info.value.status_code == 401

    def test_no_key_configured_allows_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(api_main, "ADMIN_API_KEY", "")
        api_main._ADMIN_REQUEST_HISTORY.clear()
        req = _build_request({"x-admin-user": "local-dev"})
        actor = api_main._require_admin_access(req)
        assert actor == "local-dev"


# ---------------------------------------------------------------------------
# Require Admin Access dependency wrapper
# ---------------------------------------------------------------------------
class TestRequireAdminAccessDecorator:
    def setup_method(self) -> None:
        api_main._ADMIN_REQUEST_HISTORY.clear()

    def test_dependency_rejects_unauthorized(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(api_main, "ADMIN_API_KEY", "test-key")
        dep = api_main.require_admin_access("admin")
        req = _build_request()
        with pytest.raises(HTTPException) as exc_info:
            dep(req)
        assert exc_info.value.status_code == 401

    def test_dependency_allows_authorized(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(api_main, "ADMIN_API_KEY", "test-key")
        monkeypatch.setattr(api_main, "ADMIN_ALLOWED_ROLES", {"admin"})
        dep = api_main.require_admin_access("admin")
        req = _build_request({
            "x-admin-key": "test-key",
            "x-admin-role": "admin",
            "x-admin-user": "ci-bot",
        })
        result = dep(req)
        assert result == "ci-bot"


# ---------------------------------------------------------------------------
# Idempotency Cache (TASK.md item 6)
# ---------------------------------------------------------------------------
class TestIngestIdempotencyCache:
    def setup_method(self) -> None:
        api_main._INGEST_IDEMPOTENCY_CACHE.clear()

    def test_remembers_and_retrieves(self) -> None:
        api_main._remember_ingest_idempotency("key-1", "run-abc")
        result = api_main._get_existing_run_for_idempotency("key-1")
        assert result == "run-abc"

    def test_returns_none_for_unknown_key(self) -> None:
        result = api_main._get_existing_run_for_idempotency("nonexistent")
        assert result is None

    def test_returns_none_for_none_key(self) -> None:
        result = api_main._get_existing_run_for_idempotency(None)
        assert result is None

    def test_prune_keeps_recent(self) -> None:
        api_main._remember_ingest_idempotency("recent-1", "run-1")
        api_main._prune_ingest_idempotency_cache()
        result = api_main._get_existing_run_for_idempotency("recent-1")
        assert result == "run-1"
